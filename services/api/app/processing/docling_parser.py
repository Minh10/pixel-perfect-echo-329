"""Docling-based layout-aware parser (primary).

Docling's standard PDF pipeline runs a layout model (headings, paragraphs, tables, pictures,
captions, page furniture) and TableFormer for table structure.  Model weights are fetched from
HuggingFace on first use, or loaded from `FINAUDIT_DOCLING_ARTIFACTS_PATH` (the Docker image pre-downloads
them at build time).  If they cannot be loaded we raise `ParserUnavailable`, never guess.
"""

from __future__ import annotations

import importlib.metadata
import json
import math
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.config import Settings
from app.processing.geometry import Box
from app.processing.model import RawBlock, RawCell, RawPageScores, RawParse, RawTable


class ParserUnavailable(RuntimeError):
    """The parser (or its models) cannot be initialised in this environment."""


class ParseFailed(RuntimeError):
    """The parser ran but could not convert this document."""


_ROLE_MAP = {
    "title": "title", "section_header": "section_header", "text": "text", "paragraph": "text",
    "list_item": "list_item", "caption": "caption", "footnote": "footnote", "page_header": "page_header",
    "page_footer": "page_footer", "formula": "formula", "code": "code", "table": "table",
    "document_index": "table", "picture": "picture", "chart": "chart",
}

_converter_lock = threading.Lock()
_converter_cache: dict[tuple, Any] = {}


def docling_version() -> str | None:
    try:
        return importlib.metadata.version("docling")
    except importlib.metadata.PackageNotFoundError:
        return None


def _options_key(s: Settings) -> tuple:
    return (s.docling_do_ocr, s.docling_table_structure, s.docling_picture_classification,
            s.docling_num_threads, s.docling_device, s.docling_document_timeout_s, str(_artifacts_path(s)))


def _artifacts_path(s: Settings) -> Path | None:
    p = s.docling_artifacts_path
    return p if p is not None and p.is_dir() and any(p.iterdir()) else None


def parser_options(s: Settings) -> dict[str, object]:
    return {
        "ocr": s.docling_do_ocr,
        "tableStructure": s.docling_table_structure,
        "pictureClassification": s.docling_picture_classification,
        "device": s.docling_device,
    }


def get_converter(s: Settings):
    """Build (once per process) and initialise a DocumentConverter.  Loads models eagerly."""
    key = _options_key(s)
    with _converter_lock:
        if key in _converter_cache:
            return _converter_cache[key]
        try:
            from docling.datamodel.accelerator_options import AcceleratorOptions
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption

            opts = PdfPipelineOptions(
                artifacts_path=_artifacts_path(s),
                do_ocr=s.docling_do_ocr,
                do_table_structure=s.docling_table_structure,
                do_picture_classification=s.docling_picture_classification,
                generate_page_images=False,
                generate_picture_images=False,
                document_timeout=s.docling_document_timeout_s,
                accelerator_options=AcceleratorOptions(num_threads=s.docling_num_threads, device=s.docling_device),
            )
            conv = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})
            conv.initialize_pipeline(InputFormat.PDF)  # forces model load now, not mid-job
        except Exception as exc:
            raise ParserUnavailable(
                f"Docling could not be initialised ({type(exc).__name__}: {exc}). "
                "Model weights must be downloadable from HuggingFace or present under FINAUDIT_DOCLING_ARTIFACTS_PATH."
            ) from exc
        _converter_cache[key] = conv
        return conv


def _nan_to_none(v: float | None) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else round(f, 4)


def _box(bbox, page_height: float) -> Box:
    tl = bbox.to_top_left_origin(page_height=page_height)
    return Box(min(tl.l, tl.r), min(tl.t, tl.b), max(tl.l, tl.r), max(tl.t, tl.b))


def _table(item, page_height: float) -> RawTable:
    data = item.data
    cells: list[RawCell] = []
    for c in data.table_cells:
        cells.append(
            RawCell(
                row=c.start_row_offset_idx, col=c.start_col_offset_idx,
                row_span=max(1, c.end_row_offset_idx - c.start_row_offset_idx),
                col_span=max(1, c.end_col_offset_idx - c.start_col_offset_idx),
                text=(c.text or "").strip(),
                column_header=bool(c.column_header), row_header=bool(c.row_header),
                bbox=_box(c.bbox, page_height) if c.bbox is not None else None,
            )
        )
    return RawTable(num_rows=data.num_rows, num_cols=data.num_cols, cells=cells)


def _figure_classes(item) -> list[tuple[str, float | None, str | None]]:
    meta = getattr(item, "meta", None)
    cls = getattr(meta, "classification", None) if meta else None
    if not cls:
        return []
    return [(p.class_name, _nan_to_none(p.confidence), p.created_by) for p in cls.predictions]


def docling_document_to_raw(doc, *, options: dict[str, object], version: str,
                            scores: dict[int, RawPageScores] | None = None) -> RawParse:
    """Map a DoclingDocument to the parser-neutral representation.  Pure function (unit-tested)."""
    from docling_core.types.doc import ContentLayer, TableItem, TextItem

    sizes = {int(no): (float(p.size.width), float(p.size.height)) for no, p in doc.pages.items()}
    blocks: dict[int, list[RawBlock]] = {n: [] for n in sizes}
    ref_to_pos: dict[tuple[str, int], tuple[int, int]] = {}
    caption_refs: list[tuple[int, int, list[str]]] = []

    for item, _level in doc.iterate_items(included_content_layers={ContentLayer.BODY, ContentLayer.FURNITURE}):
        label = str(getattr(item.label, "value", item.label))
        role = _ROLE_MAP.get(label, "other")
        for prov in getattr(item, "prov", None) or []:
            page_no = int(prov.page_no)
            if page_no not in sizes:
                continue
            _, ph = sizes[page_no]
            rb = RawBlock(
                page=page_no, role=role, bbox=_box(prov.bbox, ph), method="docling:layout-model",
                charspan=tuple(prov.charspan) if prov.charspan else None, source_ref=item.self_ref,
            )
            if isinstance(item, TableItem):
                rb.table = _table(item, ph)
                rb.method = "docling:layout-model+tableformer" if options.get("tableStructure") else rb.method
            elif role in ("picture", "chart"):
                rb.figure_classes = _figure_classes(item)
            elif isinstance(item, TextItem):
                rb.text = item.text
                lvl = getattr(item, "level", None)
                rb.level = int(lvl) if lvl is not None else None
            caps = [c.cref for c in (getattr(item, "captions", None) or [])]
            if caps:
                caption_refs.append((page_no, len(blocks[page_no]), caps))
            ref_to_pos[(item.self_ref, page_no)] = (page_no, len(blocks[page_no]))
            blocks[page_no].append(rb)

    for page_no, idx, caps in caption_refs:
        for cref in caps:
            pos = ref_to_pos.get((cref, page_no))
            if pos:
                blocks[page_no][idx].caption_index = pos[1]
                break

    return RawParse(parser="docling", parser_version=version, options=options, page_sizes=sizes,
                    blocks=blocks, scores=scores or {}, native_json=json.dumps(doc.export_to_dict()))


def parse_with_docling(pdf_path: Path, s: Settings, on_page: Callable[[int, int], None] | None = None) -> RawParse:
    from docling.datamodel.base_models import ConversionStatus

    conv = get_converter(s)

    def _cb(event) -> None:
        if on_page and getattr(event, "kind", None) == "page_completed":
            on_page(int(event.completed_pages), int(event.total_pages))

    try:
        res = conv.convert(pdf_path, raises_on_error=False, progress_callback=_cb)
    except Exception as exc:
        raise ParseFailed(f"Docling conversion raised {type(exc).__name__}: {exc}") from exc
    if res.status not in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
        msgs = "; ".join(e.error_message for e in res.errors) or str(res.status)
        raise ParseFailed(f"Docling conversion status {res.status.value}: {msgs}")

    scores: dict[int, RawPageScores] = {}
    for page_no, sc in (res.confidence.pages or {}).items():
        # Keyed by Docling Page.page_no, which is 1-based (base_pipeline: Page(page_no=i + 1)).
        scores[int(page_no)] = RawPageScores(
            layout_score=_nan_to_none(sc.layout_score), parse_score=_nan_to_none(sc.parse_score),
            table_score=_nan_to_none(sc.table_score), ocr_score=_nan_to_none(sc.ocr_score),
        )
    raw = docling_document_to_raw(res.document, options=parser_options(s), version=docling_version() or "unknown",
                                  scores=scores)
    if res.status == ConversionStatus.PARTIAL_SUCCESS:
        raw.warnings.append("Docling reported partial success: " + "; ".join(e.error_message for e in res.errors))
    return raw
