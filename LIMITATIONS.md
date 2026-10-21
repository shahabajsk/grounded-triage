# Limitations

What this does not do, and what I would change before a real deployment.

## Known failures

**Legitimate repeat purchases read as duplicates.** Three cases in the eval: two charges, same merchant, same amount, both delivered. The rule model credits them. Fix: check delivery records for both transactions before calling a duplicate, and add order ids to the transaction record. A stronger model may catch it; the eval will say.

**Stolen known devices escalate.** A thief using the customer's own phone looks like the customer. The model is unsure and the policy escalates. Safe, but slow. Fix needs a signal this dataset doesn't have: a lost-device report, a SIM swap flag, or a sudden change in UPI behaviour.

## What the verifier does not catch

- **Wrong reasoning over true facts.** "The device is unknown [cust:C001]" passes if the citation exists, even when the device is in fact known. The verifier checks values, not inferences. An LLM judge for inference checks is the next layer (ADR 0002).
- **Values written in words.** "Two thousand rupees" is not parsed. Drafts are instructed to use digits; a production version should normalise or reject spelled-out numbers.
- **Omissions.** A note can be fully grounded and still leave out the fact that matters. That is a recall problem; it needs a checklist per category, not a grounding check.

## Data

All 60 cases are synthetic and generated from a fixed seed. Real dispute data is messier: partial reversals, multi-currency, chargebacks already filed with the network, merchant responses. The ledger interface is built so those become new record types the verifier already knows how to check.

## Not built

- Auth, PII masking, audit log storage. Each is a client-specific integration.
- A queue. Disputes run one at a time.
- Prompt and model version pinning in the report beyond the model name.
