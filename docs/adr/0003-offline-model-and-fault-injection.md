# ADR 0003: Offline rule model and fault injection for the eval

Status: accepted

## Context

An eval that needs an API key doesn't run in CI, doesn't run for a reviewer cloning the repo, and changes every time the provider updates a model. It also can't prove the verifier works, because a good model may never fabricate during the test run.

## Decision

- The model sits behind a two-method interface (`classify`, `draft`).
- `RuleModel` is deterministic and offline. It is the CI baseline and is deliberately imperfect on three planted scenarios.
- `FabricatingModel` wraps any model and corrupts a fixed share of drafts in three ways seen in real outputs: a shifted amount, an uncited invented date, a citation to a record that doesn't exist.
- `ClaudeModel` runs the same harness against the API when a key is present.

## Consequences

- `pytest` checks that 80% injected fabrication still ships zero unverified notes.
- The baseline numbers are pinned in a test so the README table can't drift from the code.
- Real model numbers come from `--claude` runs and should be reported with the model id and date. They are not committed as the headline result because they move.
