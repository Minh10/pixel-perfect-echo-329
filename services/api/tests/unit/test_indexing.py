"""Stage 1: layout-aware chunking, structured store, deterministic re-indexing, Qdrant vectors."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.indexing import vectors
from app.indexing.chunker import DocMeta, chunk_flat, chunk_layout, detect_units, normalize_table
from app.indexing.store import ChunkStore, analyze, fts_query
from app.processing.assemble import assemble
from app.processing.pymupdf_parser import inspect_pages, parse_with_pymupdf
from app.retrieval.search import Retriever, rrf
from app.storage.db import Repository
from tests.helpers import HashEmbedder

FIX = Path(__file__).parents[1] / "fixtures" / "annual_report_excerpt.pdf"
META = DocMeta("doc_syn", "Synthetic AR", "Fictional Example Holdings plc", "2025", "Annual Report", "0" * 64,
               "pymupdf", "2.0", "job_x")


@pytest.fixture(scope="module")
def parse():
    return assemble(parse_with_pymupdf(FIX), inspect_pages(FIX), document_id="doc_syn", job_id="job_x",
                    sha256="0" * 64)


def test_table_chunk_keeps_labels_periods_units_caption(parse) -> None:
    chunks = chunk_layout(parse, META)
    table = next(c for c in chunks if c.kind == "table")
    assert table.pages == [2] and table.section_path[-1] == "Financial review"
    assert "Table 1: Summary income statement (GBP m), synthetic data" in table.content
    assert "Columns: 2025 | 2024 | Change" in table.content
    assert "Revenue: 2025 = 4,812; 2024 = 4,281; Change = +12.4%" in table.content
    assert table.meta["units"] and "millions" in table.meta["units"].lower()
    assert table.blocks[0].block_id == "p2-b003"  # cites the table block
    assert "Fictional Example Holdings plc" in table.search_text and "2025" in table.search_text
    # the caption is folded into the table chunk, not repeated as a text chunk
    assert not any(c.kind == "text" and "Table 1:" in c.content for c in chunks)


def test_figure_chunk_has_caption_context_and_crop(parse) -> None:
    fig = next(c for c in chunk_layout(parse, META) if c.kind == "figure")
    assert "Figure 1: Revenue by segment, 2025 (synthetic)" in fig.content
    assert "North remained the largest segment" in fig.content
    assert fig.meta["imageUrl"].endswith("/blocks/p3-b002/image")
    assert {b.block_id for b in fig.blocks} == {"p3-b002", "p3-b003"}


def test_chunk_ids_are_deterministic(parse) -> None:
    a = [c.chunk_id for c in chunk_layout(parse, META)]
    b = [c.chunk_id for c in chunk_layout(parse, META)]
    assert a == b and len(set(a)) == len(a)
    other = DocMeta(**{**META.__dict__, "document_id": "doc_other"})
    assert set(a).isdisjoint(c.chunk_id for c in chunk_layout(parse, other))


def test_flat_chunks_are_page_windows_with_bbox() -> None:
    flat = chunk_flat(FIX, META)
    assert [c.pages for c in flat] == [[1], [2], [3]]
    assert all(c.kind == "window" and c.section_path == [] for c in flat)
    assert flat[1].blocks[0].bbox[1] < flat[1].blocks[0].bbox[3]


def test_normalize_table_merges_currency_and_drops_empty_columns(parse) -> None:
    from app.schemas import PageBlock, TableCell, TableData

    block = next(b for b in parse.pages[1].blocks if b.kind == "table")
    cells = [TableCell(row=0, col=0, text="(Millions)"), TableCell(row=0, col=3, text="2018"),
             TableCell(row=1, col=0, text="Net income"), TableCell(row=1, col=1, text="$"),
             TableCell(row=1, col=3, text="5,363")]
    pb = PageBlock(**{**block.model_dump(), "table": TableData(columns=[], rows=[], num_rows=2, num_cols=4,
                                                               header_rows=1, cells=cells)})
    nt = normalize_table(pb)
    assert nt.columns == ["(Millions)", "2018"]
    assert nt.rows == [(1, "Net income", ["$5,363"])]


@pytest.mark.parametrize(("text", "unit"), [
    ("(In millions, except per share amounts)", "millions"), ("$ in thousands", "thousands"),
    ("Dollars in billions", "billions"), ("Revenue grew strongly", None)])
def test_detect_units(text: str, unit: str | None) -> None:
    got = detect_units(text)
    assert (got is None) if unit is None else (unit in got.lower())


def test_analyzer_normalises_numbers() -> None:
    assert analyze("Capex was $1,577 million (12.4%)") == "capex was 1577 million 12_4"
    assert fts_query("1,577 capex capex") == '"1577" OR "capex"'
    assert fts_query("?!") is None


def test_rrf() -> None:
    fused = rrf({"a": ["x", "y", "z"], "b": ["y", "x"]}, k=60)
    assert [c for c, _ in fused[:2]] == ["x", "y"] or [c for c, _ in fused[:2]] == ["y", "x"]
    assert dict(fused)["z"] == pytest.approx(1 / 63)
    assert dict(fused)["y"] == pytest.approx(1 / 62 + 1 / 61)


def _setup(tmp_path: Path, parse):
    s = Settings(data_dir=tmp_path, embedder="none")
    repo = Repository(s.db_path)
    repo.create_document_with_job({"id": "doc_syn", "title": "t", "issuer": META.company, "period": "2025",
                                   "doc_type": None, "filename": "f.pdf", "size_bytes": 1, "sha256": "0" * 64,
                                   "page_count": 3}, "pymupdf", 1)
    return s, repo, ChunkStore(s.db_path)


PROV = {"source_sha256": "0" * 64, "parser": "pymupdf", "parser_version": "2.0", "parse_job_id": "job_x"}


def test_reindex_never_duplicates_and_delete_cascades(tmp_path: Path, parse) -> None:
    s, repo, store = _setup(tmp_path, parse)
    chunks = chunk_layout(parse, META)
    for _ in range(3):
        store.replace_document_chunks("doc_syn", "layout", "layout-v1", chunks, PROV)
    assert store.count("doc_syn", "layout") == len(chunks) == store.fts_count("doc_syn")
    hits = store.bm25("operating profit 2025", "layout", ["doc_syn"], 5)
    assert hits and store.get([hits[0][0]])[hits[0][0]]["kind"] == "table"
    repo.delete_document("doc_syn")  # FK cascade + trigger remove chunks *and* FTS rows
    assert store.count("doc_syn") == 0 and store.fts_count("doc_syn") == 0


def test_qdrant_vectors_idempotent_and_searchable(tmp_path: Path, parse) -> None:
    s, _, store = _setup(tmp_path, parse)
    emb = HashEmbedder()
    chunks = chunk_layout(parse, META)
    store.replace_document_chunks("doc_syn", "layout", "layout-v1", chunks, PROV)
    vi = vectors.VectorIndex(s, "layout", emb.id, emb.dim)
    for _ in range(2):
        vi.replace_document("doc_syn", [c.chunk_id for c in chunks], emb.embed_documents([c.search_text for c in chunks]),
                            [{"kind": c.kind} for c in chunks])
    assert vi.count("doc_syn") == len(chunks)
    r = Retriever(s, store=store, embedder=emb)
    res = r.search("Revenue by segment figure", method="hybrid", chunk_set="layout", document_ids=["doc_syn"], k=3)
    assert res.effective_method == "bm25+dense" and res.hits
    assert {"bm25", "dense"} & set(res.hits[0].method_ranks)
    vectors.delete_document_everywhere(s, "doc_syn")
    assert vi.count("doc_syn") == 0
    vectors.close_clients()


def test_hybrid_degrades_to_bm25_with_warning(tmp_path: Path, parse) -> None:
    s, _, store = _setup(tmp_path, parse)
    store.replace_document_chunks("doc_syn", "layout", "layout-v1", chunk_layout(parse, META), PROV)
    res = Retriever(s, store=store).search("operating profit", method="hybrid", chunk_set="layout")
    assert res.effective_method == "bm25" and res.hits
    assert any("dense retrieval unavailable" in w for w in res.warnings)
    assert any("degraded" in w for w in res.warnings)


def test_real_onnx_embedder_if_present() -> None:
    from app.retrieval.embeddings import EmbedderUnavailable, OnnxSentenceEmbedder

    try:
        e = OnnxSentenceEmbedder(Path("models/all-MiniLM-L6-v2"))
    except EmbedderUnavailable:
        pytest.skip("ONNX model not fetched (python -m app.retrieval.fetch_models)")
    v = e.embed_documents(["Net revenue increased", "Litigation related to PFAS"])
    q = e.embed_query("How did revenue change?")
    assert v.shape == (2, 384) and abs(float((v[0] ** 2).sum()) - 1) < 1e-4
    assert float(q @ v[0]) > float(q @ v[1])


def test_data_row_is_never_a_header_and_periods_recovered_from_context(parse) -> None:
    """Regression (layout-v1 bug found on Boeing's 10-K): PyMuPDF flagged a data row as the header, so values
    were serialised under other values' labels.  v2 only accepts header rows without non-year numbers and
    recovers periods from the text above the table when the count matches the value columns exactly."""
    from app.indexing.chunker import _emit_table
    from app.schemas import PageBlock, TableCell, TableData

    page = parse.pages[1]
    tb = next(b for b in page.blocks if b.kind == "table")
    rows = [["Commercial Airplanes", "$25,867", "$19,493", "$16,162"],
            ["Defense, Space & Security", "23,162", "26,540", "26,257"]]
    cells = [TableCell(row=r, col=c, text=v, column_header=(r == 0)) for r, row in enumerate(rows) for c, v in enumerate(row)]
    pb = PageBlock(**{**tb.model_dump(), "caption_block_id": None,
                      "table": TableData(columns=[], rows=[], num_rows=2, num_cols=4, header_rows=1, cells=cells)})
    ctx = PageBlock(**{**page.blocks[1].model_dump(), "text": "(Dollars in millions) Years ended December 31, 2022 2021 2020"})
    out: list = []
    _emit_table(out, pb, page, META, [], "hdr", [ctx, pb], [ctx])
    content = out[0].content
    assert "Commercial Airplanes: 2022 = $25,867; 2021 = $19,493; 2020 = $16,162" in content
    assert "Defense, Space & Security: 2022 = 23,162" in content and "$25,867 =" not in content
    assert out[0].meta["columnsSource"] == "context" and out[0].meta["units"] == "(Dollars in millions)"
    # mismatched year count: leave columns unlabelled rather than guess
    ctx2 = PageBlock(**{**ctx.model_dump(), "text": "December 31, 2022 and 2021 and 2020 and 2019"})
    out2: list = []
    _emit_table(out2, pb, page, META, [], "hdr", [ctx2, pb], [ctx2])
    assert "Commercial Airplanes: $25,867; $19,493; $16,162" in out2[0].content
    assert out2[0].meta["columnsSource"] is None


def test_dense_falls_back_to_bm25_when_embedder_unavailable(tmp_path: Path, parse) -> None:
    s, _, store = _setup(tmp_path, parse)
    store.replace_document_chunks("doc_syn", "layout", "layout-v1", chunk_layout(parse, META), PROV)
    res = Retriever(s, store=store).search("operating profit", method="dense", chunk_set="layout")
    assert res.effective_method == "bm25" and res.hits
    assert "dense degraded to bm25 only" in res.warnings
