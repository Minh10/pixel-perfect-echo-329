"""Evaluation metrics (retrieval, answers, citations, abstention) and paired statistics.

Retrieval relevance is page-level, following FinanceBench's evidence annotation: a retrieved chunk is
relevant if it lies on a gold (document, page).  Because several chunks can sit on one gold page, gains
are de-duplicated: a chunk earns gain 1 only if it covers a gold page not covered by a higher-ranked chunk.
    Recall@k = |gold pages covered by top-k| / |gold pages|
    Hit@k    = 1 if any gold page is covered by top-k
    MRR      = 1 / rank of the first relevant chunk (0 if none in the ranking)
    nDCG@k   = DCG of the de-duplicated gains / ideal DCG (min(k, |gold|) leading 1s)
"""

from __future__ import annotations

import math
import random
import re
from collections.abc import Callable, Sequence
from decimal import Decimal, InvalidOperation

Page = tuple[str, int]  # (document_id, 1-based page)


def _new_gold(ranked: Sequence[set[Page]], gold: set[Page]) -> list[int]:
    seen: set[Page] = set()
    gains = []
    for pages in ranked:
        new = (pages & gold) - seen
        gains.append(1 if new else 0)
        seen |= new
    return gains


def recall_at_k(ranked: Sequence[set[Page]], gold: set[Page], k: int) -> float:
    covered: set[Page] = set()
    for pages in ranked[:k]:
        covered |= pages & gold
    return len(covered) / len(gold) if gold else float("nan")


def hit_at_k(ranked: Sequence[set[Page]], gold: set[Page], k: int) -> float:
    return float(any(pages & gold for pages in ranked[:k]))


def mrr(ranked: Sequence[set[Page]], gold: set[Page]) -> float:
    for i, pages in enumerate(ranked, start=1):
        if pages & gold:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: Sequence[set[Page]], gold: set[Page], k: int) -> float:
    gains = _new_gold(ranked[:k], gold)
    dcg = sum(g / math.log2(i + 2) for i, g in enumerate(gains))
    ideal = sum(1 / math.log2(i + 2) for i in range(min(k, len(gold))))
    return dcg / ideal if ideal else float("nan")


# --------------------------------------------------------------------------- numbers & answers
_NUM = re.compile(r"\(?-?\$?\s?\d[\d,]*(?:\.\d+)?\)?\s?%?")


def parse_number(text: str) -> Decimal | None:
    """Parse a financial number: '$1,577.00' -> 1577.00, '(370)' -> -370, '16.5%' -> 16.5, '-0.02'."""
    t = text.strip().replace("−", "-").replace("–", "-")
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").replace("$", "").replace(",", "").replace("%", "").strip()
    if t.startswith("+"):
        t = t[1:]
    try:
        v = Decimal(t)
    except InvalidOperation:
        return None
    return -v if neg else v


def numbers_in(text: str) -> list[Decimal]:
    out = []
    for m in _NUM.finditer(text):
        v = parse_number(m.group(0))
        if v is not None:
            out.append(v)
    return out


def numeric_match(pred: Decimal | float | None, gold: Decimal | float, rel_tol: float = 0.01,
                  abs_tol: float = 0.005) -> bool:
    """Match within 1% relative (FinanceBench answers are often rounded) or a small absolute tolerance."""
    if pred is None:
        return False
    p, g = float(pred), float(gold)
    return abs(p - g) <= max(abs_tol, rel_tol * abs(g))


def token_f1(pred: str, gold: str) -> float:
    tok = lambda s: re.findall(r"[a-z0-9]+", s.lower())  # noqa: E731
    p, g = tok(pred), tok(gold)
    if not p or not g:
        return float(p == g)
    common = 0
    gc = {}
    for t in g:
        gc[t] = gc.get(t, 0) + 1
    for t in p:
        if gc.get(t, 0):
            common += 1
            gc[t] -= 1
    if not common:
        return 0.0
    prec, rec = common / len(p), common / len(g)
    return 2 * prec * rec / (prec + rec)


def citation_pr(cited: set[Page], gold: set[Page]) -> tuple[float, float]:
    """Page-level citation precision/recall.  No citations -> precision undefined (nan), recall 0."""
    if not cited:
        return float("nan"), 0.0 if gold else float("nan")
    hit = cited & gold
    return len(hit) / len(cited), (len(hit) / len(gold) if gold else float("nan"))


def abstention_scores(rows: Sequence[tuple[bool, bool]]) -> dict[str, float]:
    """rows: (should_abstain, did_abstain).  Precision/recall/F1 of the abstain decision."""
    tp = sum(1 for s, d in rows if s and d)
    fp = sum(1 for s, d in rows if not s and d)
    fn = sum(1 for s, d in rows if s and not d)
    prec = tp / (tp + fp) if tp + fp else float("nan")
    rec = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * prec * rec / (prec + rec) if tp else 0.0
    return {"precision": prec, "recall": rec, "f1": f1, "false_abstain_rate":
            fp / max(1, sum(1 for s, _ in rows if not s)), "n_unanswerable": float(tp + fn)}


# --------------------------------------------------------------------------- statistics
def mean(xs: Sequence[float]) -> float:
    vals = [x for x in xs if not math.isnan(x)]
    return sum(vals) / len(vals) if vals else float("nan")


def bootstrap_ci(xs: Sequence[float], n: int = 2000, seed: int = 13, alpha: float = 0.05) -> tuple[float, float]:
    vals = [x for x in xs if not math.isnan(x)]
    if not vals:
        return float("nan"), float("nan")
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(vals) for _ in vals) / len(vals) for _ in range(n))
    return means[int(alpha / 2 * n)], means[int((1 - alpha / 2) * n) - 1]


def paired_test(a: Sequence[float], b: Sequence[float], n: int = 10000, seed: int = 13) -> dict[str, float]:
    """Paired comparison of per-query scores: mean difference (b - a), bootstrap 95% CI and a two-sided
    sign-flip permutation p-value."""
    pairs = [(x, y) for x, y in zip(a, b, strict=True) if not (math.isnan(x) or math.isnan(y))]
    d = [y - x for x, y in pairs]
    if not d:
        return {"diff": float("nan"), "ci_low": float("nan"), "ci_high": float("nan"), "p": float("nan"), "n": 0}
    obs = sum(d) / len(d)
    rng = random.Random(seed)
    lo, hi = bootstrap_ci(d, n=2000, seed=seed)
    extreme = sum(1 for _ in range(n) if abs(sum(x if rng.random() < 0.5 else -x for x in d) / len(d)) >= abs(obs) - 1e-12)
    return {"diff": obs, "ci_low": lo, "ci_high": hi, "p": (extreme + 1) / (n + 1), "n": len(d)}


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    """Holm-Bonferroni adjusted p-values (family-wise error control over all listed comparisons)."""
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m, adj, running = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        adj[k] = running
    return adj


def percentile(xs: Sequence[float], q: float) -> float:
    s = sorted(xs)
    if not s:
        return float("nan")
    i = (len(s) - 1) * q
    lo, hi = math.floor(i), math.ceil(i)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


Scorer = Callable[[Sequence[set[Page]], set[Page]], float]
