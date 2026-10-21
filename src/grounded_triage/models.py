"""Domain models for card-dispute triage.

Everything the agent is allowed to state about a case has to trace back to one of
these records. The verifier enforces that rule; these types are what it checks against.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Category(str, Enum):
    UNAUTHORIZED = "unauthorized"  # card used without the customer's consent
    DUPLICATE = "duplicate_charge"  # same merchant, same amount, charged twice
    NOT_RECEIVED = "not_received"  # paid, goods or service never delivered
    AMOUNT_MISMATCH = "amount_mismatch"  # charged more than the agreed amount
    NO_BASIS = "no_basis"  # evidence contradicts the claim


class Action(str, Enum):
    PROVISIONAL_CREDIT = "provisional_credit"
    REJECT = "reject"
    ESCALATE = "escalate"


class Transaction(BaseModel):
    id: str
    customer_id: str
    merchant_id: str
    amount: int = Field(description="Amount in whole rupees")
    date: str = Field(description="ISO date, YYYY-MM-DD")
    channel: str = Field(description="pos | ecom | upi")
    device_id: str | None = None
    city: str


class Merchant(BaseModel):
    id: str
    name: str
    category: str
    dispute_rate: float = Field(description="Share of this merchant's transactions disputed in the last 90 days")


class Delivery(BaseModel):
    id: str
    transaction_id: str
    status: str = Field(description="delivered | in_transit | failed")
    date: str | None = None


class Customer(BaseModel):
    id: str
    name: str
    home_city: str
    known_devices: list[str]
    prior_disputes: int


class Dispute(BaseModel):
    id: str
    customer_id: str
    transaction_id: str
    complaint: str
    claimed_amount: int | None = Field(
        default=None, description="What the customer says they agreed to pay, if they say"
    )


class Case(BaseModel):
    """A dispute plus ground truth labels, used by the eval harness."""

    dispute: Dispute
    expected_category: Category
    expected_action: Action


class Evidence(BaseModel):
    """Everything the agent gathered for one dispute. The only allowed source of facts."""

    dispute: Dispute
    customer: Customer
    transaction: Transaction
    merchant: Merchant
    related_transactions: list[Transaction] = Field(default_factory=list)
    delivery: Delivery | None = None
    related_deliveries: list[Delivery] = Field(default_factory=list)

    def records(self) -> dict[str, BaseModel]:
        """Every record the draft may cite, keyed by citation tag, e.g. 'txn:T0001'."""
        out: dict[str, BaseModel] = {
            f"dispute:{self.dispute.id}": self.dispute,
            f"cust:{self.customer.id}": self.customer,
            f"txn:{self.transaction.id}": self.transaction,
            f"merchant:{self.merchant.id}": self.merchant,
        }
        for t in self.related_transactions:
            out[f"txn:{t.id}"] = t
        if self.delivery:
            out[f"delivery:{self.delivery.id}"] = self.delivery
        for d in self.related_deliveries:
            out[f"delivery:{d.id}"] = d
        return out


class Classification(BaseModel):
    category: Category
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
