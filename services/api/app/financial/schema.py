"""Structured financial evidence schema (normalization layer, versioned separately from parsing).

A FinancialFact is one value cell of one parsed table, bound — only where the source allows — to its row,
column/period, scale, currency and scope.  The original parse (cells, bboxes, text) is never modified; facts
are derived from it and carry `cell_text` verbatim plus the cell bbox, so every normalized value traces back to
a PDF cell.  Unknown metadata stays explicitly unknown: nothing is inferred from a document title alone.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas import ApiModel, BBox

NORMALIZATION_VERSION = "facts-v1"

PeriodType = Literal["annual", "quarterly", "ytd", "cumulative", "point_in_time", "unknown"]
PeriodSource = Literal["column_header", "column_header_geometric", "narrative_clause", "unknown"]
Scale = Literal["units", "thousands", "millions", "billions", "percent", "per_share", "unknown"]
Scope = Literal["consolidated", "segment", "unknown"]
ValueStatus = Literal["parsed", "nil", "malformed", "non_numeric", "empty"]


class PeriodInfo(ApiModel):
    label: str | None = Field(default=None, description="Verbatim column header text the period was read from")
    fiscal_year: int | None = None
    end_date: str | None = Field(default=None, description="ISO date when a full date is printed (e.g. 2022-12-31)")
    period_type: PeriodType = "unknown"
    source: PeriodSource = "unknown"


class FinancialFact(ApiModel):
    fact_id: str
    normalization_version: str = NORMALIZATION_VERSION
    document_id: str
    issuer: str | None
    source_sha256: str
    table_id: str = Field(description="Parsed table block id (e.g. p56-b006)")
    page: int
    row_index: int = Field(description="Row index in the parsed table grid")
    col_indices: list[int] = Field(description="Parsed grid columns merged into this value (e.g. '$' + number)")
    slot_index: int = Field(description="Value column after geometric alignment (0 = leftmost value column)")
    row_label: str = Field(description="Verbatim row label")
    row_group: str | None = Field(default=None, description="Nearest preceding label-only row (e.g. section heading)")
    column_header: str | None = Field(default=None, description="Verbatim header text aligned with this value column")
    cell_text: str = Field(description="Verbatim value text (merged with adjacent currency/percent cells)")
    value: str | None = Field(default=None, description="Exact decimal value; null unless value_status='parsed'")
    value_status: ValueStatus
    is_percent: bool = False
    period: PeriodInfo
    scale: Scale = "unknown"
    scale_source: str | None = Field(default=None, description="Verbatim text the scale was read from")
    currency: str | None = Field(default=None, description="ISO code when stated (USD...), 'dollar' when only '$'/'Dollars'")
    currency_source: str | None = None
    scope: Scope = "unknown"
    scope_source: str | None = None
    bbox: BBox | None = None
    parser: str
    parser_version: str


class ValueSlot(ApiModel):
    index: int
    x0: float
    x1: float
    header_text: str | None
    period: PeriodInfo


class TableNormalization(ApiModel):
    table_id: str
    page: int
    normalization_version: str = NORMALIZATION_VERSION
    title_context: str | None = Field(default=None, description="Verbatim text above/left of the value columns")
    units_text: str | None = None
    scale: Scale = "unknown"
    currency: str | None = None
    scope: Scope = "unknown"
    slots: list[ValueSlot]
    facts: list[FinancialFact]
    warnings: list[str] = Field(default_factory=list)
