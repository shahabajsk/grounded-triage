"""Model adapters.

The state machine depends on a two-method interface, not on a vendor. Three adapters:

* RuleModel        - deterministic heuristics. Runs offline, makes CI and the demo free.
* FabricatingModel - wraps any model and injects fabrications at a fixed rate. Used by
                     the eval harness to prove the verifier catches what it claims to.
* ClaudeModel      - Anthropic Messages API. Optional; needs ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import json
import os
import random
import re
from typing import Protocol

from .models import Category, Classification, Evidence


class Model(Protocol):
    name: str

    def classify(self, ev: Evidence) -> Classification: ...

    def draft(self, ev: Evidence, cls: Classification, feedback: list[str] | None = None) -> str: ...


def _inr(n: int) -> str:
    return f"₹{n:,}"


# ---------------------------------------------------------------------------
# Offline deterministic model
# ---------------------------------------------------------------------------


class RuleModel:
    name = "rule-v1"

    def classify(self, ev: Evidence) -> Classification:
        t, c, d = ev.transaction, ev.customer, ev.dispute
        complaint = d.complaint.lower()

        dup = [r for r in ev.related_transactions if r.amount == t.amount]
        if dup:
            return Classification(
                category=Category.DUPLICATE,
                confidence=0.95,
                rationale=f"{len(dup)} same-amount charge(s) at the same merchant within 3 days",
            )

        unknown_device = t.device_id is not None and t.device_id not in c.known_devices
        away = t.city != c.home_city
        if unknown_device and away:
            return Classification(
                category=Category.UNAUTHORIZED,
                confidence=0.9,
                rationale="new device and a city other than the customer's home city",
            )

        if d.claimed_amount is not None and d.claimed_amount < t.amount:
            return Classification(
                category=Category.AMOUNT_MISMATCH,
                confidence=0.85,
                rationale="charged amount exceeds the amount the customer says they agreed to",
            )

        if ev.delivery is not None:
            if ev.delivery.status != "delivered":
                return Classification(
                    category=Category.NOT_RECEIVED, confidence=0.9, rationale=f"delivery status is {ev.delivery.status}"
                )
            if "not received" in complaint or "never arrived" in complaint or "never got" in complaint:
                return Classification(
                    category=Category.NO_BASIS, confidence=0.85, rationale="delivery record shows delivered"
                )

        if "didn't make" in complaint or "not me" in complaint or "unauthori" in complaint:
            # Customer claims fraud but the device and city are known. Could be a family
            # member, could be friendly fraud. The model should not be confident here.
            return Classification(
                category=Category.NO_BASIS,
                confidence=0.55,
                rationale="claims unauthorised use, but device and city match the customer",
            )

        return Classification(category=Category.NO_BASIS, confidence=0.4, rationale="no supporting signal found")

    def draft(self, ev: Evidence, cls: Classification, feedback: list[str] | None = None) -> str:
        t, m, d = ev.transaction, ev.merchant, ev.dispute
        tc, mc, dc = f"[txn:{t.id}]", f"[merchant:{m.id}]", f"[dispute:{d.id}]"
        lines = [f"Dispute {d.id} concerns a charge of {_inr(t.amount)} at {m.name} on {t.date} {tc} {dc}."]

        if cls.category is Category.DUPLICATE:
            for r in ev.related_transactions:
                if r.amount == t.amount:
                    lines.append(
                        f"A second charge of {_inr(r.amount)} at the same merchant posted on {r.date} [txn:{r.id}]."
                    )
            lines.append("The pattern is consistent with a duplicate charge.")
        elif cls.category is Category.UNAUTHORIZED:
            lines.append(f"The transaction was made in {t.city} from device {t.device_id} {tc}.")
            cc = f"[cust:{ev.customer.id}]"
            lines.append(f"The customer's home city is {ev.customer.home_city} and the device is not on file {cc}.")
        elif cls.category is Category.AMOUNT_MISMATCH:
            lines.append(f"The customer states the agreed amount was {_inr(d.claimed_amount or 0)} {dc}.")
            lines.append(f"The posted amount is {_inr(t.amount)} {tc}.")
        elif cls.category is Category.NOT_RECEIVED and ev.delivery:
            lines.append(f"The logistics record shows status {ev.delivery.status} [delivery:{ev.delivery.id}].")
        elif ev.delivery:
            dd = ev.delivery
            lines.append(f"The logistics record shows the order delivered on {dd.date} [delivery:{dd.id}].")
        else:
            lines.append("No record contradicts the transaction as posted.")

        if m.dispute_rate >= 0.05:
            lines.append(f"This merchant's 90-day dispute rate is {round(m.dispute_rate * 100, 1)}% {mc}.")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fault injection
# ---------------------------------------------------------------------------


class FabricatingModel:
    """Wraps a model and corrupts a share of its drafts in ways real models do:
    a wrong amount, an invented date, or a citation to a record that does not exist."""

    def __init__(self, inner: Model, rate: float, seed: int = 7) -> None:
        self.inner = inner
        self.rate = rate
        self.rng = random.Random(seed)
        self.name = f"{inner.name}+fabricate@{rate:.0%}"
        self.injected = 0

    def classify(self, ev: Evidence) -> Classification:
        return self.inner.classify(ev)

    def draft(self, ev: Evidence, cls: Classification, feedback: list[str] | None = None) -> str:
        text = self.inner.draft(ev, cls, feedback)
        if self.rng.random() >= self.rate:
            return text
        self.injected += 1
        mode = self.rng.choice(["amount", "date", "record"])
        if mode == "amount":
            return re.sub(r"₹([0-9,]+)", lambda m_: _inr(int(m_.group(1).replace(",", "")) + 500), text, count=1)
        if mode == "date":
            return text + "\nThe customer first reported the issue on 2026-01-15."
        return text + f"\nA matching refund was already issued [txn:{ev.transaction.id}-R]."


# ---------------------------------------------------------------------------
# Anthropic adapter
# ---------------------------------------------------------------------------

SYSTEM = """You triage card disputes for a bank's back office.
Use only the records provided. Every sentence that states an amount, date, percentage
or record id must end with a citation tag from the allowed list, e.g. [txn:T0001].
Never state a value that is not on a record you cite. Write plain sentences, no markdown."""


class ClaudeModel:
    def __init__(self, model: str | None = None) -> None:
        import anthropic  # optional dependency

        self.client = anthropic.Anthropic()
        self.model = model or os.environ.get("GT_MODEL", "claude-sonnet-5-5")
        self.name = self.model

    def _ask(self, prompt: str, max_tokens: int = 600) -> str:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()

    def classify(self, ev: Evidence) -> Classification:
        cats = ", ".join(c.value for c in Category)
        prompt = (
            f"Records:\n{ev.model_dump_json(indent=2)}\n\n"
            f"Classify the dispute into one of: {cats}.\n"
            'Reply with JSON only: {"category": ..., "confidence": 0-1, "rationale": "one sentence"}'
        )
        raw = self._ask(prompt, 300)
        raw = raw[raw.find("{") : raw.rfind("}") + 1]
        return Classification(**json.loads(raw))

    def draft(self, ev: Evidence, cls: Classification, feedback: list[str] | None = None) -> str:
        tags = ", ".join(f"[{k}]" for k in ev.records())
        prompt = (
            f"Records:\n{ev.model_dump_json(indent=2)}\n\nAllowed citation tags: {tags}\n"
            f"Category decided: {cls.category.value} ({cls.rationale}).\n"
            "Write a 3-5 sentence resolution note for the case file."
        )
        if feedback:
            prompt += "\n\nYour previous draft failed verification:\n- " + "\n- ".join(feedback) + "\nFix every issue."
        return self._ask(prompt)
