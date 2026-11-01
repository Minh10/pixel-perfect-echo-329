"""API schemas for indexing, retrieval, QA, citations and chart interpretation (Milestone 3)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas import ApiModel, BBox, NormalizedBBox

RetrievalMethod = Literal["bm25", "dense", "hybrid"]
ChunkSetName = Literal["layout", "flat"]
EvidenceKind = Literal["text", "table", "figure", "window"]
ValueKind = Literal["reported", "calculated", "visual_estimate"]


# --------------------------------------------------------------------------- citations / evidence
class CitedRegion(ApiModel):
    page: int
    block_id: str | None = None
    bbox: BBox
    bbox_normalized: NormalizedBBox
    role: str | None = None
    workspace_evidence_id: str | None = Field(
        default=None, description="Matching Evidence.id in GET /documents/{id}/evidence ('ev-{blockId}'), if any")


class ChunkRef(ApiModel):
    """A retrievable evidence chunk with exact source locations."""

    chunk_id: str
    chunk_set: ChunkSetName
    kind: EvidenceKind
    document_id: str
    document_title: str | None = None
    company: str | None = None
    period: str | None = None
    pages: list[int]
    section_path: list[str]
    content: str
    regions: list[CitedRegion]
    table: dict | None = Field(default=None, description="caption, title, units, columns, rowRange for table chunks")
    figure: dict | None = Field(default=None, description="caption, classification, imageUrl for figure chunks")
    page_image_url: str
    source_sha256: str
    parser: str
    parser_version: str
    index_version: str


class RankedEvidence(ApiModel):
    rank: int
    score: float = Field(description="Fusion/method score used for ranking (not a probability)")
    method_scores: dict[str, float]
    method_ranks: dict[str, int]
    rerank_score: float | None = None
    chunk: ChunkRef


# --------------------------------------------------------------------------- index
class IndexRun(ApiModel):
    chunk_set: ChunkSetName
    index_version: str
    embedder_id: str | None
    status: str
    chunk_count: int
    vector_count: int
    dense_status: str
    dense_error: str | None = None
    parse_job_id: str | None = None
    seconds: float | None = None
    updated_at: str


class DocumentIndexStatus(ApiModel):
    document_id: str
    indexed: bool
    runs: list[IndexRun]
    latest_job: dict | None = None


# --------------------------------------------------------------------------- retrieval
class RetrieveRequest(ApiModel):
    query: str = Field(min_length=2, max_length=2000)
    document_ids: list[str] | None = Field(default=None, description="Restrict to these documents; null = all")
    method: RetrievalMethod = "hybrid"
    chunk_set: ChunkSetName = "layout"
    k: int = Field(default=10, ge=1, le=50)
    rerank: bool = False


class RetrieveResponse(ApiModel):
    query: str
    method: RetrievalMethod
    effective_method: str
    chunk_set: ChunkSetName
    embedder_id: str | None
    reranker: str | None
    warnings: list[str]
    timings_ms: dict[str, float]
    results: list[RankedEvidence]


# --------------------------------------------------------------------------- QA
class QARequest(ApiModel):
    question: str = Field(min_length=3, max_length=2000)
    document_ids: list[str] | None = Field(default=None, description="Restrict to these documents; null = route automatically")
    top_k: int | None = Field(default=None, ge=1, le=20)
    method: RetrievalMethod | None = None
    chunk_set: ChunkSetName | None = None
    include_figures: bool = Field(default=True, description="Attach chart interpretations (visual estimates) when available")


class Operand(ApiModel):
    id: str
    value: str
    quote: str
    label: str
    evidence_id: str
    scale: str
    value_kind: Literal["reported", "visual_estimate"]
    evidence_kind: EvidenceKind
    row_label: str | None = Field(default=None, description="Source row label / metric phrase quoted by the model")
    period: str | None = Field(default=None, description="Period claimed by the model (verified against the source)")
    metric: str | None = None
    currency: str | None = None
    fact_id: str | None = Field(default=None, description="Bound FinancialFact (table evidence normalized as facts)")
    period_type: str | None = Field(default=None, description="Period type of the bound source column")
    binding: Literal["fact", "table_text", "statement", "figure"] | None = Field(
        default=None, description="How the operand was bound to evidence")


class Calculation(ApiModel):
    id: str
    op: str
    description: str
    inputs: list[dict]
    result: str
    scale: str
    value_kind: Literal["reported", "visual_estimate"]


class AnswerValue(ApiModel):
    value: str = Field(description="Exact decimal result from the deterministic calculator or a quoted operand")
    unit: str | None
    value_kind: ValueKind
    source: str = Field(description="operand or calculation id")


class Citation(ApiModel):
    evidence_id: str = Field(description="Label used in this answer, e.g. 'E2'")
    quote: str | None
    evidence_kind: EvidenceKind
    chunk: ChunkRef


class Abstention(ApiModel):
    reason: Literal["no_evidence", "insufficient_evidence", "validation_failed", "model_refused"]
    detail: str


class ValidationReport(ApiModel):
    passed: bool
    checks: list[dict]
    repaired: bool = False


class Usage(ApiModel):
    provider: str | None
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    llm_calls: int
    cost_usd: float | None = Field(default=None, description="Only when prices are configured; never estimated")


class QAResponse(ApiModel):
    status: Literal["answered", "abstained"]
    question: str
    answer: str | None
    value: AnswerValue | None
    operands: list[Operand]
    calculations: list[Calculation]
    citations: list[Citation]
    abstention: Abstention | None
    documents_considered: list[dict]
    retrieved: list[RankedEvidence]
    validation: ValidationReport | None
    usage: Usage
    timings_ms: dict[str, float]
    warnings: list[str]
    note: str = "Answers are generated from retrieved evidence and validated deterministically; they are not audited facts."


# --------------------------------------------------------------------------- charts
class ChartPoint(ApiModel):
    series: str | None
    label: str
    value: str = Field(description="Value as read from the image (string, verbatim number)")
    unit: str | None
    period: str | None = Field(default=None, description="Reporting period printed for this point, when visible")
    value_kind: Literal["visual_estimate"] = "visual_estimate"
    printed_on_chart: bool = Field(description="True if the number is printed as a data label; still not authoritative")


class TableCheck(ApiModel):
    label: str
    estimate: str
    table_value: str | None
    table_chunk_id: str | None
    relative_difference: float | None
    status: Literal["consistent", "conflict", "no_table_evidence"]
    fact_id: str | None = None
    page: int | None = None
    period: str | None = None
    absolute_difference: str | None = None


class ChartInterpretation(ApiModel):
    document_id: str
    block_id: str
    chart_type: str | None
    title: str | None
    summary: str | None = None
    points: list[ChartPoint]
    table_checks: list[TableCheck]
    crop_url: str
    provider: str
    model: str
    created_at: str
    caveat: str = (
        "Printed labels and visual estimates are distinguished on each point. "
        "Chart readings are not reported table figures."
    )
