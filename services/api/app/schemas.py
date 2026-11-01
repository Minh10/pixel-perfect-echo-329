"""Public API schemas (v1).

All models serialise to camelCase to match `src/lib/api/types.ts` in the frontend.
Fields the frontend already knows keep their names and meaning; new fields are additive.

Coordinate convention for every bbox in this API:
  * unit: PDF points (1/72 inch), origin: top-left of the (rotation-applied) page,
    `l < r`, `t < b`.  `bboxNormalized` expresses the same box as fractions of page size,
    which is what a frontend overlay on a rendered page image needs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, serialize_by_alias=True)


# --------------------------------------------------------------------------- enums
DocumentStatus = Literal["processing", "ready", "failed"]  # identical to frontend DocumentStatus
DocumentType = Literal["Annual Report", "Quarterly Report", "Prospectus", "Sustainability Report"]
JobState = Literal["queued", "running", "succeeded", "failed"]
JobStage = Literal["queued", "inspecting", "parsing", "assembling", "persisting", "done"]
ParserName = Literal["docling", "pymupdf"]

# Frontend BlockKind is "heading" | "paragraph" | "table" | "chart".  This milestone never emits
# "chart" because no chart *data* is extracted; detected figure/chart regions use "figure".
BlockKind = Literal["heading", "paragraph", "table", "figure"]
# Finer-grained layout role reported by the parser (Docling DocItemLabel vocabulary).
BlockRole = Literal[
    "title", "section_header", "text", "list_item", "caption", "footnote",
    "page_header", "page_footer", "formula", "code", "table", "picture", "chart", "other",
]
# Frontend EvidenceCategory is "metric" | "disclosure" | "table" | "chart".  "metric" is reserved
# for future semantic extraction and is never emitted; "figure" is new.
EvidenceCategory = Literal["disclosure", "table", "figure"]


# --------------------------------------------------------------------------- geometry
class BBox(ApiModel):
    l: float
    t: float
    r: float
    b: float
    coord_origin: Literal["top-left"] = "top-left"
    unit: Literal["pt"] = "pt"


class NormalizedBBox(ApiModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(ge=0, le=1)
    height: float = Field(ge=0, le=1)


class Provenance(ApiModel):
    """Where a block came from: enough to re-locate it in the original PDF bytes."""

    document_id: str
    source_sha256: str
    page: int = Field(ge=1, description="1-based page number")
    bbox: BBox
    bbox_normalized: NormalizedBBox
    page_width: float
    page_height: float
    charspan: tuple[int, int] | None = None
    source_ref: str | None = Field(default=None, description="Parser-native reference, e.g. Docling '#/texts/12'")
    parser: ParserName
    parser_version: str
    method: str = Field(description="Extraction method, e.g. 'docling:layout-model', 'pymupdf:find_tables'")
    job_id: str


# --------------------------------------------------------------------------- blocks
class TableRow(ApiModel):
    label: str
    values: list[str]
    # Frontend `emphasis` is intentionally never set: bold/total detection would be inference.


class TableCell(ApiModel):
    row: int
    col: int
    row_span: int = 1
    col_span: int = 1
    text: str
    column_header: bool = False
    row_header: bool = False
    bbox: BBox | None = None


class TableData(ApiModel):
    """Superset of frontend TableData.  `columns`/`rows` are verbatim cell text, no normalisation."""

    columns: list[str]
    rows: list[TableRow]
    num_rows: int
    num_cols: int
    header_rows: int
    cells: list[TableCell]


class FigureClassification(ApiModel):
    class_name: str
    confidence: float | None = None
    created_by: str | None = None


class FigureData(ApiModel):
    caption: str | None = None
    classification: list[FigureClassification] = Field(
        default_factory=list, description="Only populated when the Docling picture classifier is enabled"
    )
    image_url: str


class PageBlock(ApiModel):
    id: str
    kind: BlockKind
    role: BlockRole
    text: str | None = None
    level: int | None = Field(default=None, description="Heading level when reported by the parser")
    table: TableData | None = None
    figure: FigureData | None = None
    caption_block_id: str | None = None
    bbox: BBox
    bbox_normalized: NormalizedBBox
    provenance: Provenance


class PageConfidence(ApiModel):
    """Docling page-level confidence scores (0..1); null when the parser does not report them."""

    layout_score: float | None = None
    parse_score: float | None = None
    table_score: float | None = None
    ocr_score: float | None = None


class DocumentPage(ApiModel):
    number: int
    section: str = Field(description="Most recent heading text at or before this page; '' if none")
    width: float
    height: float
    rotation: int
    has_text_layer: bool
    char_count: int
    image_count: int
    confidence: PageConfidence | None = None
    image_url: str
    blocks: list[PageBlock]


# --------------------------------------------------------------------------- evidence
class EvidenceDetection(ApiModel):
    method: str
    rule: str | None = None


class Evidence(ApiModel):
    """An addressable, provenance-backed region.  It is *not* a verified financial fact."""

    id: str
    page: int
    block_id: str
    category: EvidenceCategory
    label: str
    excerpt: str
    extracted: None = Field(default=None, description="Reserved: semantic field extraction is not implemented")
    confidence: float | None = Field(default=None, description="Parser-reported confidence if any; never invented")
    related: list[str] = Field(default_factory=list)
    detection: EvidenceDetection
    provenance: Provenance


# --------------------------------------------------------------------------- documents & jobs
class ApiError(ApiModel):
    code: str
    message: str


class ParserInfo(ApiModel):
    name: ParserName
    version: str
    options: dict[str, object] = Field(default_factory=dict)


class FinDocument(ApiModel):
    id: str
    title: str
    issuer: str | None = None
    period: str | None = None
    type: DocumentType | None = None
    pages: int
    uploaded_at: datetime
    status: DocumentStatus
    size_mb: float
    # --- additive fields
    filename: str
    sha256: str
    processed_at: datetime | None = None
    latest_job_id: str | None = None
    parser: ParserInfo | None = None
    warnings: list[str] = Field(default_factory=list)
    error: ApiError | None = None


class Job(ApiModel):
    id: str
    document_id: str
    state: JobState
    stage: JobStage
    progress: float = Field(ge=0, le=1)
    attempts: int
    max_attempts: int
    requested_parser: str
    error: ApiError | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    heartbeat_at: datetime | None = None


class UploadResponse(ApiModel):
    document: FinDocument
    job: Job


class ParseResult(ApiModel):
    """Persisted output of one successful processing job (parse.json)."""

    schema_version: Literal["1"] = "1"
    document_id: str
    job_id: str
    source_sha256: str
    parser: ParserInfo
    created_at: datetime
    warnings: list[str] = Field(default_factory=list)
    pages: list[DocumentPage]
    evidence: list[Evidence]


class Health(ApiModel):
    status: Literal["ok"]
    version: str
    parser: str
    docling_version: str | None
    pymupdf_version: str
