# ADR 0001: Explicit state machine instead of a free-form tool-calling loop

Status: accepted

## Context

Dispute triage has a fixed shape: check the transaction exists, gather records, classify, write a note, check the note, decide. A ReAct-style loop lets the model choose tools and order on every turn. That is useful for open-ended research and costly here.

A bank's risk team will ask three questions before go-live:

1. Can the agent ever credit a customer without gathering evidence first?
2. Which business rules are enforced, and where?
3. When it gets something wrong, can you show exactly which step failed?

With a free-form loop the honest answer to the first is "it shouldn't". With a state machine it is "it can't", and the test suite checks it.

## Decision

The workflow is a declared transition table. The model is called only inside `classify` and `draft`, and it returns typed output (a `Classification`, a draft string). The machine, not the model, decides what happens next. An undeclared transition raises `IllegalTransition`.

Business guards (amount limit, confidence threshold, repeat-disputer rule, retry budget) are plain code in a `Policy` object.

## Consequences

- Every run produces a trace of states with a reason at each step. The dashboard and audit log come from that for free.
- `test_every_trace_follows_declared_transitions` runs every case under 50% fabrication and checks every edge.
- Adding a step (for example, a merchant-response lookup) means editing the table and one handler. That is a code change and a review, which is the point.
- Cost: the agent cannot improvise a path the designer didn't think of. For this workload that is a feature. For exploratory investigation work (a fraud analyst's "go find what's odd") I would use a bounded tool loop inside one state, not replace the machine.
