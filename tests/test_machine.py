from pathlib import Path

import pytest

from grounded_triage.eval import load_cases, run
from grounded_triage.ledger import Ledger
from grounded_triage.llm import FabricatingModel, RuleModel
from grounded_triage.machine import TRANSITIONS, State, TriageMachine
from grounded_triage.models import Action

DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def ledger() -> Ledger:
    return Ledger.from_file(DATA / "ledger.json")


@pytest.fixture(scope="module")
def cases():
    return load_cases(DATA / "cases.json")


def test_every_trace_follows_declared_transitions(ledger, cases):
    m = TriageMachine(ledger, FabricatingModel(RuleModel(), 0.5))
    for c in cases:
        trace = m.run(c.dispute).trace
        for a, b in zip(trace, trace[1:], strict=False):
            assert b.state in TRANSITIONS[a.state], f"{c.dispute.id}: {a.state} -> {b.state}"
        assert trace[-1].state is State.DONE


def test_high_value_disputes_always_escalate(ledger, cases):
    m = TriageMachine(ledger, RuleModel())
    for c in cases:
        if ledger.get_transaction(c.dispute.transaction_id).amount > 50_000:
            assert m.run(c.dispute).action is Action.ESCALATE


def test_no_unverified_note_ships_even_under_heavy_fabrication():
    result = run(FabricatingModel(RuleModel(), 0.8), DATA)
    assert result["fabrications_injected"] > 0
    assert result["fabricated_notes_shipped"] == 0


def test_offline_baseline_is_pinned():
    # If this moves, the README table is out of date. Update both together.
    r = run(RuleModel(), DATA)
    assert (r["unsafe_auto_decisions"], r["over_escalations"]) == (3, 3)
