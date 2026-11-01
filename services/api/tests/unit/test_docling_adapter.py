"""Docling -> API mapping, exercised on a DoclingDocument built with docling-core.

This tests our adapter (coordinate conversion, roles, tables, captions, classification, provenance)
independently of Docling's ML models.  The models themselves are covered by the
`docling_models`-marked integration test, which skips when weights are unavailable.
"""

from docling_core.types.doc import (
    BoundingBox,
    CoordOrigin,
    DocItemLabel,
    DoclingDocument,
    ProvenanceItem,
    Size,
    TableCell,
    TableData,
)
from docling_core.types.doc.items.picture.meta import (
    PictureClassificationMetaField,
    PictureClassificationPrediction,
    PictureMeta,
)

from app.processing.assemble import assemble
from app.processing.docling_parser import docling_document_to_raw
from app.processing.model import PageInspection, RawPageScores

PW, PH = 600.0, 800.0


def _prov(page: int, l: float, top: float, r: float, bottom: float, n: int = 0) -> ProvenanceItem:
    """Build a BOTTOMLEFT provenance from top-left coordinates (as Docling emits for PDFs)."""
    return ProvenanceItem(
        page_no=page,
        bbox=BoundingBox(l=l, t=PH - top, r=r, b=PH - bottom, coord_origin=CoordOrigin.BOTTOMLEFT),
        charspan=(0, n),
    )


def _doc() -> DoclingDocument:
    doc = DoclingDocument(name="fixture")
    doc.add_page(page_no=1, size=Size(width=PW, height=PH))
    doc.add_page(page_no=2, size=Size(width=PW, height=PH))
    doc.add_title("Annual Report 2025", prov=_prov(1, 50, 40, 400, 70, 18))
    doc.add_text(DocItemLabel.PAGE_HEADER, "Fictional plc", prov=_prov(1, 50, 10, 200, 20, 13))
    doc.add_heading("Financial review", level=1, prov=_prov(1, 50, 90, 250, 110, 16))
    doc.add_text(DocItemLabel.TEXT, "Revenue rose 12.4% to £4,812 million.", prov=_prov(1, 50, 120, 500, 140, 37))
    doc.add_text(DocItemLabel.TEXT, "We continued to invest in people.", prov=_prov(1, 50, 150, 500, 170, 33))

    cells = []
    for r, row in enumerate([["", "2025", "2024"], ["Revenue", "4,812", "4,281"]]):
        for c, text in enumerate(row):
            cells.append(TableCell(
                text=text, start_row_offset_idx=r, end_row_offset_idx=r + 1, start_col_offset_idx=c,
                end_col_offset_idx=c + 1, column_header=(r == 0),
                bbox=BoundingBox(l=50 + c * 100, t=200 + r * 20, r=150 + c * 100, b=220 + r * 20,
                                 coord_origin=CoordOrigin.TOPLEFT),
            ))
    caption = doc.add_text(DocItemLabel.CAPTION, "Table 1: Income statement", prov=_prov(1, 50, 245, 300, 258, 25))
    doc.add_table(data=TableData(num_rows=2, num_cols=3, table_cells=cells), caption=caption,
                  prov=_prov(1, 50, 200, 350, 240))

    pic = doc.add_picture(prov=_prov(2, 60, 100, 460, 400))
    pic.meta = PictureMeta(classification=PictureClassificationMetaField(predictions=[
        PictureClassificationPrediction(class_name="bar_chart", confidence=0.93, created_by="test-classifier")
    ]))
    return doc


def _assembled():
    raw = docling_document_to_raw(_doc(), options={"tableStructure": True, "ocr": False}, version="2.x-test",
                                  scores={1: RawPageScores(layout_score=0.9, parse_score=float("nan"))})
    insp = [PageInspection(n, PW, PH, 0, 100, 0) for n in (1, 2)]
    return raw, assemble(raw, insp, document_id="doc_t", job_id="job_t", sha256="f" * 64)


def test_roles_kinds_and_order() -> None:
    _, res = _assembled()
    p1 = res.pages[0]
    assert [(b.kind, b.role) for b in p1.blocks] == [
        ("heading", "title"), ("paragraph", "page_header"), ("heading", "section_header"),
        ("paragraph", "text"), ("paragraph", "text"), ("paragraph", "caption"), ("table", "table"),
    ]
    assert p1.section == "Annual Report 2025"
    assert res.pages[1].section == "Financial review"  # carried over to a page without headings


def test_bbox_converted_from_bottom_left_and_provenance_complete() -> None:
    _, res = _assembled()
    title = res.pages[0].blocks[0]
    assert (title.bbox.l, title.bbox.t, title.bbox.r, title.bbox.b) == (50, 40, 400, 70)
    assert title.bbox_normalized.y == round(40 / PH, 5)
    prov = title.provenance
    assert prov.parser == "docling" and prov.parser_version == "2.x-test"
    assert prov.source_ref == "#/texts/0" and prov.charspan == (0, 18)
    assert prov.document_id == "doc_t" and prov.job_id == "job_t" and prov.source_sha256 == "f" * 64
    assert prov.method == "docling:layout-model"


def test_table_cells_caption_and_evidence() -> None:
    _, res = _assembled()
    table = res.pages[0].blocks[-1]
    assert table.provenance.method == "docling:layout-model+tableformer"
    assert table.table.columns == ["", "2025", "2024"]
    assert table.table.rows[0].label == "Revenue" and table.table.rows[0].values == ["4,812", "4,281"]
    assert table.table.cells[0].bbox.t == 200  # TOPLEFT cell box preserved
    assert table.caption_block_id == res.pages[0].blocks[5].id
    ev = {e.block_id: e for e in res.evidence}
    assert ev[table.id].category == "table" and ev[table.id].label == "Table 1: Income statement"
    assert ev[table.id].extracted is None and ev[table.id].confidence is None


def test_figure_classification_is_passed_through_not_invented() -> None:
    _, res = _assembled()
    fig = res.pages[1].blocks[0]
    assert fig.kind == "figure" and fig.role == "picture"
    assert fig.figure.classification[0].class_name == "bar_chart"
    assert fig.figure.classification[0].confidence == 0.93
    assert fig.figure.image_url.endswith(f"/blocks/{fig.id}/image")
    assert (fig.bbox.t, fig.bbox.b) == (100, 400)
    ev = next(e for e in res.evidence if e.block_id == fig.id)
    assert ev.category == "figure" and "bar_chart" in ev.label


def test_only_numeric_text_becomes_disclosure_evidence() -> None:
    _, res = _assembled()
    disclosures = [e for e in res.evidence if e.category == "disclosure"]
    assert [e.excerpt for e in disclosures] == ["Revenue rose 12.4% to £4,812 million."]
    assert disclosures[0].detection.rule.startswith("numeric-disclosure-v1")


def test_page_scores_nan_becomes_null() -> None:
    _, res = _assembled()
    assert res.pages[0].confidence.layout_score == 0.9
    assert res.pages[0].confidence.parse_score is None
    assert res.pages[1].confidence is None


def test_native_json_round_trips() -> None:
    raw, _ = _assembled()
    restored = DoclingDocument.model_validate_json(raw.native_json)
    assert restored.texts[0].text == "Annual Report 2025"
