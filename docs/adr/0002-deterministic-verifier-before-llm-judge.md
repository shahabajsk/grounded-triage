# ADR 0002: Deterministic grounding checks before any LLM judge

Status: accepted

## Context

The common way to catch hallucinated content is a second model call: "does this note match these records?" It works most of the time. The problem is "most". If the judge misses 2% of fabrications, the bank has a 2% rate of false statements in its case files, and nobody can say which 2%.

Most fabrications that matter in a dispute note are values: amounts, dates, ids, rates. Those can be checked exactly.

## Decision

1. Drafts must cite records inline, `[txn:T00045]`, from a list the model is given.
2. A deterministic verifier checks every sentence: a value needs a citation, the citation must exist, and the value must equal a field on a cited record (not just any record).
3. Failures go back to the model as specific feedback. After three attempts the case escalates and no note ships.
4. An LLM judge, when added, sits after this layer and handles what code cannot: whether an inference follows from the cited facts, tone, and policy wording.

## Consequences

- "Unverified notes shipped" is a number the eval can hold at zero and CI can fail on.
- The verifier is about 100 lines and has unit tests for each failure kind.
- Fault injection makes the claim testable: the harness corrupts drafts at 20% and 40% and the shipped count stays at zero.
- It is strict. A model that writes "about ₹2,000" for a ₹1,987 charge fails. That is the right default for a financial record; loosen it per field only with the client's sign-off.
- It does not catch wrong reasoning over true facts. See LIMITATIONS.md.
