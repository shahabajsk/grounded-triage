"""Eval harness.

Runs every case through the machine and scores it on what a bank risk team asks about:

* unsafe_auto_decisions  - auto-credited or auto-rejected, and the action was wrong. The number that matters.
* fabricated_notes_shipped - notes that left the machine with an unverified claim. Target: 0.
* over_escalations       - sent to an analyst when an automatic decision was correct. Costs time, not trust.
* automation_rate        - share of cases closed without a human.

Run with several fabrication rates to show the verifier holds the shipped rate at zero
while the cost moves into retries and escalations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ledger import Ledger
from .llm import FabricatingModel, Model, RuleModel
from .machine import Outcome, TriageMachine
from .models import Action, Case
from .verifier import verify


def load_cases(path: str | Path) -> list[Case]:
    return [Case(**c) for c in json.loads(Path(path).read_text())]


def score(cases: list[Case], outcomes: list[Outcome], ledger: Ledger) -> dict:
    n = len(cases)
    by_id = {c.dispute.id: c for c in cases}
    unsafe = over = auto = correct = cat_ok = cat_n = shipped_bad = 0
    rows = []
    for o in outcomes:
        c = by_id[o.dispute_id]
        is_auto = o.action is not Action.ESCALATE
        auto += is_auto
        if o.action == c.expected_action:
            correct += 1
        elif is_auto:
            unsafe += 1
        elif c.expected_action is not Action.ESCALATE:
            over += 1
        if o.category is not None and is_auto:
            cat_n += 1
            cat_ok += o.category == c.expected_category
        if o.draft is not None:
            ev = ledger.gather(c.dispute)
            shipped_bad += not verify(o.draft, ev).ok
        rows.append(
            {
                "id": o.dispute_id,
                "complaint": c.dispute.complaint,
                "expected_action": c.expected_action.value,
                "expected_category": c.expected_category.value,
                "action": o.action.value,
                "category": o.category.value if o.category else None,
                "confidence": o.confidence,
                "escalation_reason": o.escalation_reason,
                "draft_attempts": o.draft_attempts,
                "verifier_rejections": o.verifier_rejections,
                "draft": o.draft,
                "verdict": "correct" if o.action == c.expected_action else ("unsafe" if is_auto else "over_escalation"),
                "trace": [{"state": s.state.value, "note": s.note} for s in o.trace],
            }
        )
    return {
        "cases": n,
        "action_accuracy": round(correct / n, 3),
        "category_accuracy_on_auto": round(cat_ok / cat_n, 3) if cat_n else None,
        "automation_rate": round(auto / n, 3),
        "unsafe_auto_decisions": unsafe,
        "over_escalations": over,
        "fabricated_notes_shipped": shipped_bad,
        "verifier_rejections": sum(o.verifier_rejections for o in outcomes),
        "rows": rows,
    }


def run(model: Model, data_dir: str | Path) -> dict:
    data_dir = Path(data_dir)
    ledger = Ledger.from_file(data_dir / "ledger.json")
    cases = load_cases(data_dir / "cases.json")
    machine = TriageMachine(ledger, model)
    outcomes = [machine.run(c.dispute) for c in cases]
    result = score(cases, outcomes, ledger)
    result["model"] = model.name
    if isinstance(model, FabricatingModel):
        result["fabrications_injected"] = model.injected
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the dispute-triage eval")
    ap.add_argument("--data", default="data")
    ap.add_argument("--rates", default="0,0.2,0.4", help="fabrication rates to sweep")
    ap.add_argument("--claude", action="store_true", help="also run the Claude adapter (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--out", default="reports/eval.json")
    args = ap.parse_args()

    runs = []
    for r in [float(x) for x in args.rates.split(",")]:
        model: Model = RuleModel() if r == 0 else FabricatingModel(RuleModel(), r)
        runs.append(run(model, args.data))
    if args.claude:
        from .llm import ClaudeModel

        runs.append(run(ClaudeModel(), args.data))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"runs": runs}, indent=1))

    hdr = f"{'model':<28}{'acc':>6}{'auto':>7}{'unsafe':>8}{'over-esc':>10}{'injected':>10}{'caught':>8}{'shipped':>9}"
    print(hdr)
    print("-" * len(hdr))
    for r in runs:
        print(
            f"{r['model']:<28}{r['action_accuracy']:>6.2f}{r['automation_rate']:>7.2f}{r['unsafe_auto_decisions']:>8}"
            f"{r['over_escalations']:>10}{r.get('fabrications_injected', 0):>10}{r['verifier_rejections']:>8}"
            f"{r['fabricated_notes_shipped']:>9}"
        )
    print(f"\nfull report: {out}")


if __name__ == "__main__":
    main()
