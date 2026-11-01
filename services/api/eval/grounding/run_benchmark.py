"""Operand-grounding benchmark: false accepts / false rejects of the evidence validator on real filings.

    PYTHONPATH=. python eval/grounding/run_benchmark.py --db <layout-v3 corpus>/finaudit.sqlite3 \
        [--legacy-db <layout-v2 corpus>/finaudit.sqlite3] --out <dir> [--export-fixtures <json>]

For each case (eval/grounding/cases_{dev,heldout}.jsonl) the evidence candidates are the indexed layout chunks
on the cited page whose content contains the quoted value -- the chunks a model could cite.  The claim is
ACCEPTED if it binds with every check passing against ANY candidate (conservative: an adversarial plan may cite
whichever chunk is most permissive).  No LLM is involved: this measures the deterministic validator only.

`--legacy-db` additionally runs the PR #2 association validator, loaded verbatim from commit ab8ed0b (with the
PR #2 number parser), on the layout-v2 index it was designed for.  Its operand label is "<metric> <period>"
(plus the currency when the claim states one), the single free-text label PR #2 asked the model for.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import types
from math import comb
from pathlib import Path

from app.indexing.store import ChunkStore
from app.qa.evidence_binding import OperandClaim, bind_table, bind_text

HERE = Path(__file__).parent
LEGACY_COMMIT = "ab8ed0b"


def squash(s: str) -> str:
    return re.sub(r"[\s$\xa0]+", "", s or "").lower()


# --------------------------------------------------------------------------- statistics
def _binom_cdf(k: int, n: int, p: float) -> float:
    return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact two-sided binomial CI (bisection on the binomial CDF)."""
    if n == 0:
        return (0.0, 1.0)

    def solve(f, lo=0.0, hi=1.0):
        for _ in range(80):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(mid) else (lo, mid)
        return (lo + hi) / 2

    lower = 0.0 if k == 0 else solve(lambda p: 1 - _binom_cdf(k - 1, n, p) < alpha / 2)
    upper = 1.0 if k == n else solve(lambda p: _binom_cdf(k, n, p) > alpha / 2)
    return lower, upper


# --------------------------------------------------------------------------- evidence
def candidates(store: ChunkStore, case: dict) -> list[dict]:
    q = squash(case["claim"]["quote"])
    return [r for r in store.chunks_for(case["doc"], "layout")
            if r["pages"] == [case["page"]] and r["kind"] == case["kind"] and q in squash(r["content"])]


def evidence_of(store: ChunkStore, row: dict) -> dict:
    meta = row.get("meta") or {}
    ev = {"chunk_id": row["chunk_id"], "kind": row["kind"], "text": row["content"],
          "context": " ".join(x for x in (meta.get("title"), meta.get("context")) if x)}
    if row["kind"] == "table":
        ids = meta.get("factIds") or []
        ev["facts"] = list(store.facts(ids).values()) if ids else []
    return ev


def bind(case: dict, ev: dict) -> list[dict]:
    cl = case["claim"]
    claim = OperandClaim(id=case["id"], quote=cl["quote"], row_label=cl["row_label"], period=cl["period"],
                         metric=cl["metric"], scale=cl["scale"], currency=cl.get("currency"))
    if ev["kind"] == "table":
        if not ev.get("facts"):
            return [{"check": "operand_facts_available", "ok": False, "detail": "chunk has no normalized facts"}]
        return bind_table(claim, ev["facts"], case["question"], context=ev.get("context", ""))[0]
    return bind_text(claim, ev["text"], case["question"])[0]


def judge(case: dict, evs: list[dict], fn) -> dict:
    per = []
    for ev in evs:
        checks = fn(case, ev)
        per.append({"chunk_id": ev["chunk_id"], "accepted": all(c["ok"] for c in checks),
                    "failed": [f"{c['check']}: {c['detail']}" for c in checks if not c["ok"]]})
    accepted = any(p["accepted"] for p in per)
    truth = case["expect"] == "accept"
    outcome = "correct" if accepted == truth else ("FALSE_ACCEPT" if accepted else "FALSE_REJECT")
    if not evs:
        outcome = "NO_EVIDENCE" if truth else "correct"
    return {"accepted": accepted, "outcome": outcome, "candidates": per}


# --------------------------------------------------------------------------- PR #2 validator (verbatim)
def load_legacy():
    def src(path: str) -> str:
        return subprocess.run(["git", "show", f"{LEGACY_COMMIT}:services/api/{path}"], capture_output=True,
                              text=True, check=True).stdout

    metrics = types.ModuleType("legacy_metrics")
    exec(compile(src("app/evaluation/metrics.py"), "legacy_metrics", "exec"), metrics.__dict__)  # noqa: S102
    saved = sys.modules.get("app.evaluation.metrics")
    sys.modules["app.evaluation.metrics"] = metrics
    try:
        mod = types.ModuleType("legacy_pipeline")
        sys.modules["legacy_pipeline"] = mod  # dataclasses resolve their module through sys.modules
        code = src("app/qa/pipeline.py")
        exec(compile(code, "legacy_pipeline", "exec"), mod.__dict__)  # noqa: S102
    finally:
        if saved is not None:
            sys.modules["app.evaluation.metrics"] = saved
    return mod.operand_association_checks


def legacy_fn(assoc):
    def fn(case: dict, ev: dict) -> list[dict]:
        cl = case["claim"]
        label = f"{cl['metric']} {cl['period']}" + (f" ({cl['currency']})" if cl.get("currency") else "")
        return assoc(kind=ev["kind"], label=label, quote=cl["quote"], scale=cl["scale"], text=ev["text"],
                     question=case["question"], units=ev.get("units"))
    return fn


# --------------------------------------------------------------------------- report
def summarize(rows: list[dict], key: str) -> dict:
    out = {}
    for split in ("dev", "heldout", "heldout2", "heldout3", "heldout4"):
        rs = [r for r in rows if r["split"] == split]
        if not rs:
            continue
        neg = [r for r in rs if r["expect"] == "reject"]
        pos = [r for r in rs if r["expect"] == "accept"]
        fa = [r["id"] for r in neg if r[key]["outcome"] == "FALSE_ACCEPT"]
        fr = [r["id"] for r in pos if r[key]["outcome"] in ("FALSE_REJECT", "NO_EVIDENCE")]
        out[split] = {"cases": len(rs), "should_reject": len(neg), "should_accept": len(pos),
                      "false_accepts": len(fa), "false_accept_ids": fa,
                      "false_accept_rate": round(len(fa) / len(neg), 4) if neg else None,
                      "false_accept_ci95": [round(x, 4) for x in clopper_pearson(len(fa), len(neg))],
                      "false_rejects": len(fr), "false_reject_ids": fr,
                      "false_reject_rate": round(len(fr) / len(pos), 4) if pos else None,
                      "false_reject_ci95": [round(x, 4) for x in clopper_pearson(len(fr), len(pos))],
                      "documents": sorted({r["doc"] for r in rs})}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--legacy-db", type=Path)
    ap.add_argument("--splits", default="dev,heldout,heldout2,heldout3,heldout4")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--export-fixtures", type=Path)
    args = ap.parse_args()
    cases = []
    for split in args.splits.split(","):
        cases += [json.loads(x) for x in (HERE / f"cases_{split}.jsonl").read_text().splitlines()]
    store = ChunkStore(args.db)
    legacy = None
    if args.legacy_db:
        legacy_store, assoc = ChunkStore(args.legacy_db), load_legacy()
        legacy = (legacy_store, legacy_fn(assoc))
    rows, fixtures = [], []
    for case in cases:
        evs = [evidence_of(store, r) for r in candidates(store, case)]
        row = dict(case, m35=judge(case, evs, bind))
        if legacy:
            lst, lfn = legacy
            levs = [dict(evidence_of(lst, r), units=(r.get("meta") or {}).get("units")) for r in candidates(lst, case)]
            row["pr2"] = judge(case, levs, lfn)
        rows.append(row)
        fixtures.append({"case": case, "evidence": evs, "m35_accepted": row["m35"]["accepted"]})
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(rows, indent=1))
    summary = {"validator_m35": summarize(rows, "m35")}
    if legacy:
        summary["validator_pr2"] = summarize(rows, "pr2")
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1))
    if args.export_fixtures:
        args.export_fixtures.parent.mkdir(parents=True, exist_ok=True)
        args.export_fixtures.write_text(json.dumps(fixtures, indent=1))
    for name, s in summary.items():
        for split, v in s.items():
            print(f"{name:14} {split:8} n={v['cases']:3}  FA {v['false_accepts']}/{v['should_reject']} "
                  f"CI95 {v['false_accept_ci95']}  FR {v['false_rejects']}/{v['should_accept']} "
                  f"CI95 {v['false_reject_ci95']}")
            print(f"{'':24}FA ids {v['false_accept_ids']}  FR ids {v['false_reject_ids']}")
    for r in rows:
        line = f"{r['id']} {r['split']:7} expect={r['expect']:6} m35={r['m35']['outcome']:13}"
        if legacy:
            line += f" pr2={r['pr2']['outcome']:13}"
        print(line + f" {r['category']}")
        if r["m35"]["outcome"] != "correct":
            for p in r["m35"]["candidates"]:
                for f in p["failed"]:
                    print(f"      x {f}")


if __name__ == "__main__":
    main()
