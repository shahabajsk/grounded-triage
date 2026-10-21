"""Explicit state machine for one dispute.

The model never chooses the next step. It is called inside two states (CLASSIFY and
DRAFT) and its output is checked before the machine moves on. Every transition is
declared up front, so an illegal jump is a bug that raises, not a behaviour that ships.
See docs/adr/0001 for why this beats a free-form tool-calling loop for this workload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .ledger import Ledger
from .llm import Model
from .models import Action, Category, Classification, Dispute, Evidence
from .verifier import VerificationResult, verify


class State(str, Enum):
    INTAKE = "intake"
    GATHER = "gather_evidence"
    CLASSIFY = "classify"
    DRAFT = "draft"
    VERIFY = "verify"
    DECIDE = "decide"
    ESCALATE = "escalate"
    DONE = "done"


TRANSITIONS: dict[State, set[State]] = {
    State.INTAKE: {State.GATHER, State.ESCALATE},
    State.GATHER: {State.CLASSIFY, State.ESCALATE},
    State.CLASSIFY: {State.DRAFT, State.ESCALATE},
    State.DRAFT: {State.VERIFY},
    State.VERIFY: {State.DECIDE, State.DRAFT, State.ESCALATE},
    State.DECIDE: {State.DONE, State.ESCALATE},
    State.ESCALATE: {State.DONE},
    State.DONE: set(),
}


@dataclass
class Policy:
    """Business guards. In a real deployment these come from the client's risk team, in writing."""

    min_confidence: float = 0.7
    auto_limit_inr: int = 50_000
    max_draft_attempts: int = 3
    max_prior_disputes: int = 3


@dataclass
class Step:
    state: State
    note: str


@dataclass
class Outcome:
    dispute_id: str
    action: Action
    category: Category | None
    confidence: float | None
    draft: str | None
    escalation_reason: str | None
    draft_attempts: int
    verifier_rejections: int
    trace: list[Step] = field(default_factory=list)


class IllegalTransition(RuntimeError):
    pass


class TriageMachine:
    def __init__(self, ledger: Ledger, model: Model, policy: Policy | None = None) -> None:
        self.ledger = ledger
        self.model = model
        self.policy = policy or Policy()

    def run(self, dispute: Dispute) -> Outcome:
        state = State.INTAKE
        trace: list[Step] = []
        ev: Evidence | None = None
        cls: Classification | None = None
        draft: str | None = None
        check: VerificationResult | None = None
        attempts = 0
        rejections = 0
        reason: str | None = None
        action: Action | None = None

        def go(nxt: State, note: str) -> State:
            if nxt not in TRANSITIONS[state]:
                raise IllegalTransition(f"{state.value} -> {nxt.value}")
            trace.append(Step(state, note))  # note records what happened in the state we are leaving
            return nxt

        while state is not State.DONE:
            if state is State.INTAKE:
                try:
                    self.ledger.get_transaction(dispute.transaction_id)
                    state = go(State.GATHER, "transaction found")
                except KeyError:
                    reason = "transaction not found in ledger"
                    state = go(State.ESCALATE, reason)

            elif state is State.GATHER:
                ev = self.ledger.gather(dispute)
                if ev.transaction.amount > self.policy.auto_limit_inr:
                    reason = f"amount above auto-resolution limit of ₹{self.policy.auto_limit_inr:,}"
                    state = go(State.ESCALATE, reason)
                elif ev.customer.prior_disputes >= self.policy.max_prior_disputes:
                    reason = f"customer has {ev.customer.prior_disputes} prior disputes"
                    state = go(State.ESCALATE, reason)
                else:
                    state = go(State.CLASSIFY, f"{len(ev.records())} records gathered")

            elif state is State.CLASSIFY:
                assert ev is not None
                cls = self.model.classify(ev)
                if cls.confidence < self.policy.min_confidence:
                    reason = f"low confidence ({cls.confidence:.2f}) on {cls.category.value}"
                    state = go(State.ESCALATE, reason)
                else:
                    state = go(State.DRAFT, f"{cls.category.value} @ {cls.confidence:.2f}: {cls.rationale}")

            elif state is State.DRAFT:
                assert ev is not None and cls is not None
                feedback = [f"{i.kind}: {i.detail} | {i.sentence}" for i in check.issues] if check else None
                draft = self.model.draft(ev, cls, feedback)
                attempts += 1
                state = go(State.VERIFY, f"draft attempt {attempts}")

            elif state is State.VERIFY:
                assert ev is not None and draft is not None
                check = verify(draft, ev)
                if check.ok:
                    state = go(State.DECIDE, f"{check.sentences_checked} sentences verified")
                else:
                    rejections += 1
                    summary = "; ".join(f"{i.kind}: {i.detail}" for i in check.issues)
                    if attempts >= self.policy.max_draft_attempts:
                        reason = "draft failed verification after retries"
                        draft = None  # an unverified draft never leaves the machine
                        state = go(State.ESCALATE, summary)
                    else:
                        state = go(State.DRAFT, f"rejected: {summary}")

            elif state is State.DECIDE:
                assert cls is not None
                action = Action.REJECT if cls.category is Category.NO_BASIS else Action.PROVISIONAL_CREDIT
                state = go(State.DONE, action.value)

            elif state is State.ESCALATE:
                action = Action.ESCALATE
                state = go(State.DONE, f"queued for analyst: {reason}")

        trace.append(Step(State.DONE, action.value if action else ""))
        assert action is not None
        return Outcome(
            dispute_id=dispute.id,
            action=action,
            category=cls.category if cls else None,
            confidence=cls.confidence if cls else None,
            draft=draft,
            escalation_reason=reason if action is Action.ESCALATE else None,
            draft_attempts=attempts,
            verifier_rejections=rejections,
            trace=trace,
        )
