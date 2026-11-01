"""Static API contract check: frontend `src/lib/api/types.ts` vs backend OpenAPI component schemas.

    PYTHONPATH=. python eval/audit/contract_check.py [--strict]

For each mapped pair (TS interface -> Pydantic schema) it reports:
  * MISSING   — a *required* TS field (no `?`) that the backend schema does not define (frontend would read
                undefined: a real bug);
  * OPTIONAL  — an optional TS field the backend does not define (dead field; informational);
  * ENUM      — TS literal unions vs backend enum values that differ (e.g. a stage the UI cannot render).
Exit code 1 with --strict when any MISSING or ENUM mismatch exists (suitable for CI).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TYPES = ROOT / "src" / "lib" / "api" / "types.ts"

PAIRS = {  # TS interface -> backend schema
    "FinDocument": "FinDocument", "ParserInfo": "ParserInfo", "BBox": "BBox", "NormalizedBBox": "NormalizedBBox",
    "Provenance": "Provenance", "TableCell": "TableCell", "TableData": "TableData", "FigureData": "FigureData",
    "FigureClassification": "FigureClassification", "PageBlock": "PageBlock", "PageConfidence": "PageConfidence",
    "DocumentPage": "DocumentPage", "EvidenceDetection": "EvidenceDetection", "Evidence": "Evidence", "Job": "Job",
    "CitedRegion": "CitedRegion", "ChunkRef": "ChunkRef", "QACitation": "Citation", "QAOperand": "Operand",
    "QACalculation": "Calculation", "QAResponse": "QAResponse", "QARequest": "QARequest",
    "FinancialFact": "FinancialFact", "FactPeriod": "PeriodInfo",
}
ENUMS = {  # TS type alias -> (schema, property)
    "DocumentStatus": ("FinDocument", "status"), "JobState": ("Job", "state"), "JobStage": ("Job", "stage"),
    "BlockKind": ("PageBlock", "kind"), "EvidenceCategory": ("Evidence", "category"),
    "ValueKind": ("AnswerValue", "valueKind"), "JobKind": ("Job", "kind"),
    "FactPeriodType": ("PeriodInfo", "periodType"), "FactScale": ("FinancialFact", "scale"),
    "FactScope": ("FinancialFact", "scope"), "FactValueStatus": ("FinancialFact", "valueStatus"),
}


def parse_ts(src: str) -> tuple[dict[str, dict[str, bool]], dict[str, set[str]]]:
    interfaces: dict[str, dict[str, bool]] = {}
    for m in re.finditer(r"export interface (\w+)(?:\s+extends\s+[\w, ]+)?\s*\{", src):
        name, i, depth = m.group(1), m.end(), 1
        j = i
        while depth and j < len(src):
            depth += {"{": 1, "}": -1}.get(src[j], 0)
            j += 1
        body = src[i:j - 1]
        fields: dict[str, bool] = {}
        depth = 0
        for line in body.splitlines():
            if depth == 0:
                fm = re.match(r"\s*(\w+)(\?)?\s*:", line)
                if fm:
                    fields[fm.group(1)] = fm.group(2) is None  # True = required
            depth += line.count("{") - line.count("}")
        interfaces[name] = fields
    aliases: dict[str, set[str]] = {}
    for m in re.finditer(r"export type (\w+)\s*=\s*([^;]+);", src, re.S):
        lits = re.findall(r'"([^"]+)"', m.group(2))
        if lits and "|" in m.group(2):
            aliases[m.group(1)] = set(lits)
    return interfaces, aliases


def backend_schemas() -> dict:
    os.environ.setdefault("FINAUDIT_DATA_DIR", tempfile.mkdtemp())
    from app.main import create_app

    return create_app().openapi()["components"]["schemas"]


def enum_values(schema: dict, prop: str, schemas: dict) -> set[str] | None:
    p = schema.get("properties", {}).get(prop)
    if p is None:
        return None
    node = p
    if "$ref" in node:
        node = schemas[node["$ref"].split("/")[-1]]
    if "enum" in node:
        return set(node["enum"])
    for alt in node.get("anyOf", []):
        if "enum" in alt:
            return set(alt["enum"])
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    interfaces, aliases = parse_ts(TYPES.read_text())
    schemas = backend_schemas()
    findings = []
    for ts, be in PAIRS.items():
        if ts not in interfaces:
            findings.append(("NO_TS_TYPE", ts, be, ""))
            continue
        props = schemas.get(be, {}).get("properties", {})
        for field, required in interfaces[ts].items():
            if field not in props:
                findings.append(("MISSING" if required else "OPTIONAL", ts, be, field))
    for alias, (be, prop) in ENUMS.items():
        ts_vals = aliases.get(alias, set())
        be_vals = enum_values(schemas.get(be, {}), prop, schemas) or set()
        if be_vals - ts_vals:
            findings.append(("ENUM", alias, f"{be}.{prop}", f"backend-only values {sorted(be_vals - ts_vals)}"))
        if ts_vals - be_vals:
            findings.append(("ENUM_TS_ONLY", alias, f"{be}.{prop}", f"frontend-only values {sorted(ts_vals - be_vals)}"))
    for f in findings:
        print(" | ".join(f))
    bad = [f for f in findings if f[0] in ("MISSING", "ENUM", "NO_TS_TYPE")]
    print(f"\n{len(findings)} findings; {len(bad)} contract errors (MISSING/ENUM/NO_TS_TYPE)")
    if args.json:
        args.json.write_text(json.dumps([dict(zip(("kind", "ts", "backend", "detail"), f)) for f in findings], indent=1))
    return 1 if (args.strict and bad) else 0


if __name__ == "__main__":
    sys.exit(main())
