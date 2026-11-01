"""Answer-text grounding: numbers (fail closed) and non-numeric claims.

Every numeric-looking token in an answer is classified by `scan_numeric_tokens`:
  * value      must equal an operand or a (rounded/rescaled) calculation result, or restate the question;
               a number that merely appears in a cited excerpt is NOT accepted (it is not bound to row/period/unit);
  * year       must appear in the question or the cited evidence;
  * malformed  is never accepted (fail closed: e.g. "1,57,7" or "(7.0" in an answer is an error, not ignored);
  * reference / date tokens are identifiers, not quantities, and are reported but not grounded.
Non-numeric claims: each answer sentence must be supported by the cited evidence (content-word coverage), and
sentences that look like instructions, links or contact details are rejected outright (prompt-injection output).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal

from app.financial.numbers import numbers_in, scan_numeric_tokens

_STOP = set("""a an the of in on at to for from by with and or but as is are was were be been being this that these those
it its their his her our we you they which who whom whose than then there here into over under up down out about after
before during per each other such only also not no nor so very can could would should may might will shall do does did
has have had approximately about around roughly nearly total company company's year years fiscal reported report
reports increased decreased increase decrease change changed compared versus vs while whereas approximately""".split())
_INJECTION = re.compile(
    r"(https?://|www\.|@[a-z0-9-]+\.[a-z]{2,}|\bignore (all |any |the )?(previous|prior|above)\b|\bsystem prompt\b|"
    r"\bdisregard\b.*\binstruction|\byou are now\b|\bnew instructions?\b|\bdeveloper mode\b|\bjailbreak\b)",
    re.IGNORECASE)


def _close(n: Decimal, allowed: set[Decimal]) -> bool:
    return n in allowed or abs(n) in allowed or any(abs(abs(n) - abs(a)) < Decimal("1e-7") for a in allowed)


def number_checks(answer: str, question: str, cited_texts: Iterable[str], allowed_values: set[Decimal]) -> list[dict]:
    # A value in the answer must be an operand or a calculation result (the caller passes their rounding and
    # rescaling variants) or restate the question.  Merely appearing somewhere in a cited excerpt is NOT enough:
    # that let an answer repeat any figure from the chunk -- including one planted by injected text -- without
    # it ever being bound to a row, period and unit.
    cited = list(cited_texts)
    allowed = set(allowed_values) | set(numbers_in(question))
    years_ok = {tok.value for t in [question, *cited] for tok in scan_numeric_tokens(t) if tok.kind == "year"}
    malformed, ungrounded, bad_years = [], [], []
    for tok in scan_numeric_tokens(answer):
        if tok.kind == "malformed":
            malformed.append(tok.text)
        elif tok.kind == "value" and not _close(tok.value, allowed):
            ungrounded.append(tok.text)
        elif tok.kind == "year" and tok.value not in years_ok:
            bad_years.append(tok.text)
    return [
        {"check": "answer_numbers_wellformed", "ok": not malformed,
         "detail": f"malformed numeric text in answer: {malformed[:5]}" if malformed else ""},
        {"check": "answer_numbers_grounded", "ok": not ungrounded,
         "detail": f"numbers that are not validated operands or calculation results: {', '.join(ungrounded[:6])}" if ungrounded else ""},
        {"check": "answer_years_grounded", "ok": not bad_years,
         "detail": f"years not in the question or cited evidence: {bad_years[:5]}" if bad_years else ""},
    ]


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z&'-]{2,}", text.lower())
    return {w.strip("'") for w in words if w not in _STOP}


def claim_checks(answer: str, question: str, cited_texts: Iterable[str], min_support: float = 0.5) -> list[dict]:
    """Each answer sentence must be supported by cited evidence (or merely restate the question)."""
    support_vocab = _content_words(" ".join([question, *cited_texts]))
    injected, weak = [], []
    for sent in re.split(r"(?<=[.!?])\s+", answer.strip()):
        if not sent:
            continue
        if _INJECTION.search(sent):
            injected.append(sent[:120])
            continue
        words = _content_words(sent)
        if len(words) < 3:
            continue  # short connective sentences ("Yes.", "No change.") carry no new claim
        cover = len(words & support_vocab) / len(words)
        if cover < min_support:
            weak.append(f"{sent[:120]!r} (support {cover:.2f})")
    return [
        {"check": "answer_no_injected_content", "ok": not injected,
         "detail": f"instruction/link-like content in answer: {injected[:2]}" if injected else ""},
        {"check": "answer_claims_supported", "ok": not weak,
         "detail": f"sentences not supported by cited evidence: {weak[:2]}" if weak else ""},
    ]
