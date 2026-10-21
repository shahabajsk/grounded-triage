from grounded_triage.models import Customer, Dispute, Evidence, Merchant, Transaction
from grounded_triage.verifier import verify


def evidence() -> Evidence:
    return Evidence(
        dispute=Dispute(id="D001", customer_id="C001", transaction_id="T00001", complaint="charged twice"),
        customer=Customer(id="C001", name="Test User", home_city="Pune", known_devices=["DEV-a"], prior_disputes=0),
        transaction=Transaction(
            id="T00001",
            customer_id="C001",
            merchant_id="M100",
            amount=2400,
            date="2026-09-10",
            channel="ecom",
            device_id="DEV-a",
            city="Pune",
        ),
        merchant=Merchant(id="M100", name="Shop", category="retail", dispute_rate=0.064),
    )


def test_clean_draft_passes():
    draft = (
        "A charge of ₹2,400 posted on 2026-09-10 [txn:T00001].\nThe merchant's dispute rate is 6.4% [merchant:M100]."
    )
    assert verify(draft, evidence()).ok


def test_uncited_amount_is_flagged():
    r = verify("The customer was charged ₹2,400.", evidence())
    assert [i.kind for i in r.issues] == ["uncited_claim"]


def test_wrong_amount_is_flagged_even_with_citation():
    r = verify("A charge of ₹2,900 posted [txn:T00001].", evidence())
    assert r.issues[0].kind == "value_mismatch"


def test_wrong_date_is_flagged():
    r = verify("The charge posted on 2026-09-11 [txn:T00001].", evidence())
    assert r.issues[0].kind == "value_mismatch"


def test_citation_to_missing_record_is_flagged():
    r = verify("A refund was issued [txn:T99999].", evidence())
    assert r.issues[0].kind == "unknown_record"


def test_value_must_be_on_the_cited_record_not_any_record():
    # 2400 is a real amount, but it lives on the transaction, not the merchant
    r = verify("The merchant processed ₹2,400 [merchant:M100].", evidence())
    assert r.issues[0].kind == "value_mismatch"


def test_plain_sentence_without_values_needs_no_citation():
    assert verify("The pattern is consistent with a duplicate charge.", evidence()).ok
