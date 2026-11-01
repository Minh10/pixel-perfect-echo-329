"""Parser-neutral intermediate representation.

Each parser (Docling, PyMuPDF) emits `RawPage`s / `RawBlock`s; `assemble.py` turns them into
API schemas with IDs, sections, provenance and evidence.  This keeps provenance rules in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.processing.geometry import Box


@dataclass
class RawCell:
    row: int
    col: int
    row_span: int
    col_span: int
    text: str
    column_header: bool = False
    row_header: bool = False
    bbox: Box | None = None


@dataclass
class RawTable:
    num_rows: int
    num_cols: int
    cells: list[RawCell]


@dataclass
class RawBlock:
    page: int
    role: str  # schemas.BlockRole
    bbox: Box
    method: str
    text: str | None = None
    level: int | None = None
    table: RawTable | None = None
    figure_classes: list[tuple[str, float | None, str | None]] = field(default_factory=list)
    caption_index: int | None = None  # index into the page's block list
    charspan: tuple[int, int] | None = None
    source_ref: str | None = None


@dataclass
class RawPageScores:
    layout_score: float | None = None
    parse_score: float | None = None
    table_score: float | None = None
    ocr_score: float | None = None


@dataclass
class RawParse:
    parser: str  # "docling" | "pymupdf"
    parser_version: str
    options: dict[str, object]
    # page number -> (width, height) in the parser's coordinate frame
    page_sizes: dict[int, tuple[float, float]]
    blocks: dict[int, list[RawBlock]]
    scores: dict[int, RawPageScores] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    native_json: str | None = None  # raw DoclingDocument JSON


@dataclass
class PageInspection:
    number: int
    width: float
    height: float
    rotation: int
    char_count: int
    image_count: int

    @property
    def has_text_layer(self) -> bool:
        return self.char_count > 0
