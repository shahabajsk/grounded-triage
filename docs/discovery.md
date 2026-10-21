# Discovery: questions before building

The code in this repo has five numbers in `Policy` and a dozen judgment calls in the classifier. Every one of them should come from the client, in writing. These are the questions I use to get them, grouped by who answers.

## Dispute operations lead

- What is the monthly dispute volume, and how is it split by category today?
- What is the current time to first decision, and what is the regulatory deadline?
- Which decisions can an analyst make alone, and which need a supervisor? (Sets `auto_limit_inr`.)
- What does a good case note look like? Can I see 20 real ones, redacted, including bad ones?
- Which disputes do analysts get wrong most often today?

## Risk and compliance

- What error rate on automatic credits is acceptable? On automatic rejections? (These are different numbers. A wrong rejection is a customer complaint and possibly a regulator complaint.)
- Who signs off on the policy thresholds, and how often are they reviewed?
- What must be in the audit trail for each decision?
- Is a model-written note allowed in the case file, or does a human have to edit it?

## Data and platform

- Where do transactions, device fingerprints, merchant data and delivery status live? Which have APIs, which are batch?
- How fresh is each source? A delivery status that lags by a day breaks the "not received" logic.
- What can leave the bank's network? Can we call a hosted model, or does it need a private deployment?
- Is there a sandbox with realistic data, and how long does access take to arrange?

## Success criteria (agreed before build)

Written down in the SOW, measured in shadow mode:

| Metric | Target | Measured how |
|---|---|---|
| Unverified notes shipped | 0 | Verifier, every case |
| Wrong automatic decisions | below the current analyst error rate | Shadow mode vs analyst decision, 4 weeks |
| Automation rate | agreed with ops | Share closed without a human |
| Time to first decision | agreed with ops | Queue timestamps |
