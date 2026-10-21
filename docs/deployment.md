# Deployment plan

How this goes from repo to a bank's dispute desk. Phases are gated on numbers, not dates.

## Phase 0: integrate (2 to 3 weeks)

- Replace `ledger.py` lookups with the bank's APIs. Nothing else in the agent changes.
- Map the bank's records to the evidence model. Every field the note can mention must be on a record the verifier can see.
- Re-run the eval on 200 labelled historical disputes. Labels come from the analysts' actual decisions.

**Gate:** zero unverified notes shipped; wrong automatic decisions below the analyst baseline on the historical set.

## Phase 1: shadow mode (4 weeks)

- The agent runs on every live dispute. Analysts work as normal and don't see the agent's output.
- Daily diff: agent action vs analyst action. Every disagreement is reviewed and labelled (agent wrong, analyst wrong, ambiguous).
- Tune thresholds in `Policy` with the risk team, from this data only.

**Gate:** two consecutive weeks inside the agreed error rates, signed off by risk.

## Phase 2: assist (4 weeks)

- Analysts see the agent's proposed action, trace and note. They accept, edit or override.
- Track override rate by category. A category with a high override rate goes back to shadow.

## Phase 3: automate by category

- Turn on automatic decisions one category at a time, starting with the one with the lowest override rate (usually clean duplicates).
- Everything else stays in assist.

## What to watch in week one of each phase

| Signal | Why | Action if it moves |
|---|---|---|
| Verifier rejection rate | A jump means the model or the data changed | Check model version and source freshness |
| Escalation rate by reason | Shows which guard is doing the work | Review that guard with risk |
| Low-confidence share | Drift in the complaint mix | Sample and relabel |
| Latency per state | A slow source shows up here first | Fix the integration, not the agent |

## Failure modes I plan for

- **A source goes stale.** Delivery status stops updating; every "not received" looks real. Mitigation: freshness check in `gather_evidence`, escalate if a record is older than its SLA.
- **Model version change.** The provider updates the model and behaviour shifts. Mitigation: pin the model id, re-run the eval before any change, keep the last report for comparison.
- **Policy drift.** Someone edits a threshold to cut the queue. Mitigation: `Policy` changes go through code review with a risk approver.
