"""Run one dispute end to end and print the trace.

python -m grounded_triage run D007
python -m grounded_triage run D007 --fabricate 0.9
python -m grounded_triage list
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .eval import load_cases
from .ledger import Ledger
from .llm import FabricatingModel, Model, RuleModel
from .machine import TriageMachine


def main() -> None:
    ap = argparse.ArgumentParser(prog="grounded_triage")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="triage one dispute")
    r.add_argument("dispute_id")
    r.add_argument("--fabricate", type=float, default=0.0, help="inject fabrications at this rate")
    r.add_argument("--claude", action="store_true")
    r.add_argument("--data", default="data")
    lst = sub.add_parser("list", help="list disputes")
    lst.add_argument("--data", default="data")
    args = ap.parse_args()

    data = Path(args.data)
    cases = {c.dispute.id: c for c in load_cases(data / "cases.json")}

    if args.cmd == "list":
        for cid in sorted(cases):
            c = cases[cid]
            print(f"{cid}  {c.expected_action.value:<19} {c.dispute.complaint}")
        return

    model: Model
    if args.claude:
        from .llm import ClaudeModel

        model = ClaudeModel()
    else:
        model = RuleModel()
    if args.fabricate:
        model = FabricatingModel(model, args.fabricate)

    case = cases[args.dispute_id]
    out = TriageMachine(Ledger.from_file(data / "ledger.json"), model).run(case.dispute)

    print(f"dispute   {case.dispute.id}: {case.dispute.complaint}")
    print(f"model     {model.name}\n")
    for s in out.trace:
        print(f"  {s.state.value:<16} {s.note}")
    print(f"\naction    {out.action.value}   (expected {case.expected_action.value})")
    if out.draft:
        print("\nresolution note\n---------------")
        print(out.draft)


if __name__ == "__main__":
    main()
