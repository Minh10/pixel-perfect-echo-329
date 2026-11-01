"""Deterministic, validated financial calculations.

The LLM never runs code.  It emits a *plan*: operands (each a verbatim quote from a retrieved evidence
item) and calculation steps drawn from a fixed whitelist of operations, referencing operands or earlier
steps by id.  This module validates the plan (references, arity, division by zero, scale consistency)
and executes it with `decimal.Decimal`.  Provenance is propagated: a result is a `visual_estimate` if
any input was read from a chart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, DivisionByZero, InvalidOperation, getcontext

getcontext().prec = 28

OPS: dict[str, tuple[int, int | None, str]] = {
    # name: (min args, max args or None, description)
    "add": (2, None, "a + b + ..."),
    "subtract": (2, 2, "a - b"),
    "multiply": (2, None, "a * b * ..."),
    "divide": (2, 2, "a / b"),
    "sum": (1, None, "sum of inputs"),
    "average": (1, None, "arithmetic mean of inputs"),
    "percent_change": (2, 2, "(new - old) / |old| * 100, args [old, new]"),
    "percent_of": (2, 2, "part / whole * 100, args [part, whole]"),
    "difference_pct_points": (2, 2, "b - a for two percentages, args [a, b]"),
    "negate": (1, 1, "-a"),
    "abs": (1, 1, "|a|"),
    "cagr": (2, 2, "((end / begin) ** (1 / periods) - 1) * 100, args [begin, end], needs periods"),
}
SCALES = {"units": Decimal(1), "thousands": Decimal(10) ** 3, "millions": Decimal(10) ** 6,
          "billions": Decimal(10) ** 9, "percent": Decimal(1), "ratio": Decimal(1), "per_share": Decimal(1)}
MAX_STEPS = 20


class CalculationError(ValueError):
    pass


@dataclass
class Operand:
    id: str
    value: Decimal
    scale: str = "units"
    value_kind: str = "reported"  # "reported" | "visual_estimate"


@dataclass
class Step:
    id: str
    op: str
    args: list[str]
    periods: int | None = None
    description: str = ""


@dataclass
class StepResult:
    id: str
    op: str
    inputs: list[tuple[str, Decimal]]
    value: Decimal
    scale: str
    value_kind: str
    description: str = ""


@dataclass
class Execution:
    results: dict[str, StepResult] = field(default_factory=dict)

    def value_of(self, ref: str, operands: dict[str, Operand]) -> tuple[Decimal, str, str]:
        if ref in operands:
            o = operands[ref]
            return o.value, o.scale, o.value_kind
        if ref in self.results:
            r = self.results[ref]
            return r.value, r.scale, r.value_kind
        raise CalculationError(f"unknown reference {ref!r}")


def _result_scale(op: str, scales: list[str]) -> str:
    if op in ("percent_change", "percent_of", "cagr", "difference_pct_points"):
        return "percent"
    if op == "divide":
        return "ratio"
    if op == "multiply":
        # e.g. (USD millions) x ratio keeps USD millions; two monetary scales multiplied has no meaningful scale
        monetary = [s for s in scales if s in ("thousands", "millions", "billions")]
        return monetary[0] if len(monetary) == 1 else "units"
    return scales[0]


def execute(operands: list[Operand], steps: list[Step]) -> Execution:
    ops = {o.id: o for o in operands}
    if len(ops) != len(operands):
        raise CalculationError("duplicate operand ids")
    if len(steps) > MAX_STEPS:
        raise CalculationError(f"too many calculation steps (>{MAX_STEPS})")
    ex = Execution()
    for st in steps:
        if st.id in ops or st.id in ex.results:
            raise CalculationError(f"duplicate id {st.id!r}")
        if st.op not in OPS:
            raise CalculationError(f"operation {st.op!r} is not allowed")
        lo, hi, _ = OPS[st.op]
        if len(st.args) < lo or (hi is not None and len(st.args) > hi):
            raise CalculationError(f"{st.op} takes {lo}..{hi or 'n'} arguments, got {len(st.args)}")
        vals = [ex.value_of(a, ops) for a in st.args]  # only earlier ids resolve: no cycles possible
        nums, scales, kinds = [v[0] for v in vals], [v[1] for v in vals], [v[2] for v in vals]
        # Additive ops require a common scale; convert to absolute units when scales differ.
        if st.op in ("add", "subtract", "sum", "average") and len(set(scales)) > 1:
            if any(s in ("percent", "ratio", "per_share") for s in scales):
                raise CalculationError(f"{st.op} mixes incompatible units {scales}")
            nums = [n * SCALES[s] for n, s in zip(nums, scales, strict=True)]
            scales = ["units"] * len(nums)
        if st.op in ("divide", "percent_change", "percent_of", "cagr") and len(set(scales)) > 1:
            if not any(s in ("percent", "ratio", "per_share") for s in scales):
                nums = [n * SCALES[s] for n, s in zip(nums, scales, strict=True)]
        try:
            v = _apply(st, nums)
        except (DivisionByZero, InvalidOperation, ZeroDivisionError) as exc:
            raise CalculationError(f"{st.op} is undefined for inputs {nums}") from exc
        ex.results[st.id] = StepResult(id=st.id, op=st.op, inputs=list(zip(st.args, nums, strict=True)), value=v,
                                       scale=_result_scale(st.op, scales), description=st.description,
                                       value_kind="visual_estimate" if "visual_estimate" in kinds else "reported")
    return ex


def _apply(st: Step, n: list[Decimal]) -> Decimal:
    op = st.op
    if op in ("add", "sum"):
        return sum(n, Decimal(0))
    if op == "subtract":
        return n[0] - n[1]
    if op == "multiply":
        out = Decimal(1)
        for x in n:
            out *= x
        return out
    if op == "divide":
        if n[1] == 0:
            raise DivisionByZero
        return n[0] / n[1]
    if op == "average":
        return sum(n, Decimal(0)) / len(n)
    if op == "percent_change":
        if n[0] == 0:
            raise DivisionByZero
        return (n[1] - n[0]) / abs(n[0]) * 100
    if op == "percent_of":
        if n[1] == 0:
            raise DivisionByZero
        return n[0] / n[1] * 100
    if op == "difference_pct_points":
        return n[1] - n[0]
    if op == "negate":
        return -n[0]
    if op == "abs":
        return abs(n[0])
    if op == "cagr":
        if not st.periods or st.periods <= 0:
            raise CalculationError("cagr requires a positive integer 'periods'")
        if n[0] <= 0 or n[1] <= 0:
            raise CalculationError("cagr requires positive begin and end values")
        return (Decimal(float(n[1] / n[0]) ** (1.0 / st.periods)) - 1) * 100
    raise CalculationError(op)


def rounding_variants(v: Decimal) -> set[Decimal]:
    """Values a model might legitimately print for v (rounded to 0-4 decimals)."""
    return {v.quantize(Decimal(1).scaleb(-d)) for d in range(0, 5)}
