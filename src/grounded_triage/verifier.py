"""Zero-fabrication verifier.

Deterministic checks on a drafted resolution note before it is allowed to leave the
system. The rule is simple: every factual sentence cites a record, every cited record
exists, and every number or date in the sentence matches a field on a cited record.

This runs on every draft, independent of which model wrote it. An LLM judge can sit
on top for tone and policy, but it never replaces this layer (see docs/adr/0002).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pydantic import BaseModel

from .models import Evidence

CITATION = re.compile(r"\[((?:txn|cust|merchant|delivery|dispute):[A-Za-z0-9-]+)\]")
AMOUNT = re.compile(r"(?:₹|INR\s?|Rs\.?\s?)([0-9][0-9,]*)")
DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
PERCENT = re.compile(r"\b(\d+(?:\.\d+)?)%")
BARE_ID = re.compile(r"\b(T\d{4,}|C\d{3,}|M\d{3,}|D\d{3,}|DL\d{3,})\b")


@dataclass
class Issue:
    sentence: str
    kind: str  # uncited_claim | unknown_record | value_mismatch
    detail: str


@dataclass
class VerificationResult:
    issues: list[Issue] = field(default_factory=list)
    sentences_checked: int = 0

    @property
    def ok(self) -> bool:
        return not self.issues


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _field_values(record: BaseModel) -> tuple[set[int], set[str], set[float]]:
    ints: set[int] = set()
    strs: set[str] = set()
    floats: set[float] = set()
    for v in record.model_dump().values():
        if isinstance(v, bool):
            continue
        if isinstance(v, int):
            ints.add(v)
        elif isinstance(v, float):
            floats.add(round(v * 100, 1))
        elif isinstance(v, str):
            strs.add(v)
    return ints, strs, floats


def verify(draft: str, evidence: Evidence) -> VerificationResult:
    records = evidence.records()
    result = VerificationResult()

    for sentence in _sentences(draft):
        result.sentences_checked += 1
        cites = CITATION.findall(sentence)
        body = CITATION.sub("", sentence)

        amounts = [int(a.replace(",", "")) for a in AMOUNT.findall(body)]
        dates = DATE.findall(body)
        percents = [float(p) for p in PERCENT.findall(body)]
        bare_ids = BARE_ID.findall(body)
        is_factual = bool(amounts or dates or percents or bare_ids)

        if is_factual and not cites:
            result.issues.append(Issue(sentence, "uncited_claim", "states a value with no citation"))
            continue

        unknown = [c for c in cites if c not in records]
        if unknown:
            result.issues.append(Issue(sentence, "unknown_record", f"cites {', '.join(unknown)}"))
            continue

        ints: set[int] = set()
        strs: set[str] = set()
        floats: set[float] = set()
        for c in cites:
            i, s, f = _field_values(records[c])
            ints |= i
            strs |= s
            floats |= f

        for a in amounts:
            if a not in ints:
                result.issues.append(Issue(sentence, "value_mismatch", f"amount {a} not on any cited record"))
        for d in dates:
            if d not in strs:
                result.issues.append(Issue(sentence, "value_mismatch", f"date {d} not on any cited record"))
        for p in percents:
            if round(p, 1) not in floats:
                result.issues.append(Issue(sentence, "value_mismatch", f"{p}% not on any cited record"))
        for b in bare_ids:
            if b not in strs:
                result.issues.append(Issue(sentence, "value_mismatch", f"id {b} not on any cited record"))

    return result
