"""Synthetic dataset generator.

All names, ids, merchants and amounts are invented. The scenario mix is chosen to
include cases the offline model gets wrong, so the eval numbers mean something.

    python -m grounded_triage.synth --out data --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

from .models import Action, Case, Category, Customer, Delivery, Dispute, Merchant, Transaction

FIRST = [
    "Aarav",
    "Diya",
    "Kabir",
    "Meera",
    "Rohan",
    "Ananya",
    "Vihaan",
    "Isha",
    "Arjun",
    "Sara",
    "Neel",
    "Tara",
    "Dev",
    "Riya",
    "Kiran",
    "Zoya",
    "Aditya",
    "Naina",
    "Farhan",
    "Pooja",
]
LAST = ["Sharma", "Iyer", "Khan", "Das", "Menon", "Gupta", "Reddy", "Bose", "Nair", "Singh"]
CITIES = ["Gurugram", "Bengaluru", "Mumbai", "Pune", "Hyderabad", "Kolkata", "Chennai", "Jaipur"]
MERCHANTS = [
    ("Northwind Electronics", "electronics", 0.031),
    ("Saffron Kitchen", "food", 0.012),
    ("Bluepeak Travel", "travel", 0.064),
    ("Urban Thread", "apparel", 0.022),
    ("QuickCart Grocery", "grocery", 0.008),
    ("Pixel Arcade", "digital_goods", 0.091),
    ("Monsoon Furnishings", "home", 0.027),
    ("Velocity Fitness", "subscription", 0.071),
]

# scenario -> (expected category, expected action, count)
MIX = {
    "unauthorized": (Category.UNAUTHORIZED, Action.PROVISIONAL_CREDIT, 10),
    "duplicate": (Category.DUPLICATE, Action.PROVISIONAL_CREDIT, 8),
    "not_received": (Category.NOT_RECEIVED, Action.PROVISIONAL_CREDIT, 8),
    "amount_mismatch": (Category.AMOUNT_MISMATCH, Action.PROVISIONAL_CREDIT, 6),
    "delivered_claim": (Category.NO_BASIS, Action.REJECT, 8),
    "ambiguous_fraud": (Category.NO_BASIS, Action.ESCALATE, 6),
    "high_value": (Category.UNAUTHORIZED, Action.ESCALATE, 4),
    "repeat_disputer": (Category.NO_BASIS, Action.ESCALATE, 4),
    # Hard cases. The offline model is expected to miss these.
    "stolen_known_device": (Category.UNAUTHORIZED, Action.PROVISIONAL_CREDIT, 3),
    "legit_repeat_purchase": (Category.NO_BASIS, Action.REJECT, 3),
}

COMPLAINTS = {
    "unauthorized": "I didn't make this payment. My card was with me the whole time.",
    "duplicate": "I was charged twice for the same order.",
    "not_received": "I paid for this order but it never arrived.",
    "amount_mismatch": "The amount charged is higher than what I agreed to pay.",
    "delivered_claim": "Order not received, please refund.",
    "ambiguous_fraud": "This is not me, I don't recognise this transaction.",
    "high_value": "Unauthorised transaction on my card, I was not travelling.",
    "repeat_disputer": "I don't recognise this charge.",
    "stolen_known_device": "My phone was stolen on a trip and someone used it to pay. Not me.",
    "legit_repeat_purchase": "I was charged twice for the same order.",
}


def generate(seed: int = 42) -> tuple[dict, list[Case]]:
    rng = random.Random(seed)
    base = date(2026, 9, 1)
    merchants = [
        Merchant(id=f"M{100 + i}", name=n, category=c, dispute_rate=r) for i, (n, c, r) in enumerate(MERCHANTS)
    ]
    customers: list[Customer] = []
    txns: list[Transaction] = []
    deliveries: list[Delivery] = []
    cases: list[Case] = []

    n_txn = 0
    n_case = 0

    def new_txn(
        cust: Customer, merch: Merchant, amount: int, day: date, device: str | None, city: str, channel: str
    ) -> Transaction:
        nonlocal n_txn
        n_txn += 1
        t = Transaction(
            id=f"T{n_txn:05d}",
            customer_id=cust.id,
            merchant_id=merch.id,
            amount=amount,
            date=day.isoformat(),
            channel=channel,
            device_id=device,
            city=city,
        )
        txns.append(t)
        return t

    for scenario, (cat, action, count) in MIX.items():
        for _ in range(count):
            n_case += 1
            cid = f"C{len(customers) + 1:03d}"
            home = rng.choice(CITIES)
            dev = f"DEV-{rng.randrange(16**6):06x}"
            cust = Customer(
                id=cid,
                name=f"{rng.choice(FIRST)} {rng.choice(LAST)}",
                home_city=home,
                known_devices=[dev],
                prior_disputes=4 if scenario == "repeat_disputer" else rng.choice([0, 0, 0, 1]),
            )
            customers.append(cust)
            merch = rng.choice(merchants)
            day = base + timedelta(days=rng.randrange(40))
            amount = rng.randrange(400, 18_000)
            away = rng.choice([c for c in CITIES if c != home])
            claimed = None

            # a little ordinary history so the ledger is not one row per customer
            for _h in range(rng.randrange(1, 4)):
                new_txn(
                    cust,
                    rng.choice(merchants),
                    rng.randrange(150, 6000),
                    day - timedelta(days=rng.randrange(5, 30)),
                    dev,
                    home,
                    rng.choice(["pos", "ecom", "upi"]),
                )

            if scenario in ("unauthorized", "high_value"):
                if scenario == "high_value":
                    amount = rng.randrange(60_000, 180_000)
                t = new_txn(cust, merch, amount, day, f"DEV-{rng.randrange(16**6):06x}", away, "ecom")
            elif scenario in ("duplicate", "legit_repeat_purchase"):
                t = new_txn(cust, merch, amount, day, dev, home, "ecom")
                second = new_txn(cust, merch, amount, day + timedelta(days=rng.choice([0, 1])), dev, home, "ecom")
                if scenario == "legit_repeat_purchase":
                    # two real orders, both shipped and delivered
                    for x in (t, second):
                        deliveries.append(
                            Delivery(
                                id=f"DL{len(deliveries) + 1:04d}",
                                transaction_id=x.id,
                                status="delivered",
                                date=(day + timedelta(days=3)).isoformat(),
                            )
                        )
            elif scenario in ("not_received", "delivered_claim"):
                t = new_txn(cust, merch, amount, day, dev, home, "ecom")
                status = rng.choice(["in_transit", "failed"]) if scenario == "not_received" else "delivered"
                deliveries.append(
                    Delivery(
                        id=f"DL{len(deliveries) + 1:04d}",
                        transaction_id=t.id,
                        status=status,
                        date=(day + timedelta(days=4)).isoformat() if status == "delivered" else None,
                    )
                )
            elif scenario == "amount_mismatch":
                t = new_txn(cust, merch, amount, day, dev, home, "pos")
                claimed = amount - rng.choice([500, 1000, 1500, 2000])
            elif scenario == "stolen_known_device":
                t = new_txn(cust, merch, amount, day, dev, away, "upi")
            else:  # ambiguous_fraud, repeat_disputer
                t = new_txn(cust, merch, amount, day, dev, home, "pos")

            dispute = Dispute(
                id=f"D{n_case:03d}",
                customer_id=cid,
                transaction_id=t.id,
                complaint=COMPLAINTS[scenario],
                claimed_amount=claimed,
            )
            cases.append(Case(dispute=dispute, expected_category=cat, expected_action=action))

    rng.shuffle(cases)
    # number disputes after shuffling so ids don't leak the scenario
    cases = [
        c.model_copy(update={"dispute": c.dispute.model_copy(update={"id": f"D{i:03d}"})})
        for i, c in enumerate(cases, start=1)
    ]
    ledger = {
        "customers": [c.model_dump() for c in customers],
        "merchants": [m.model_dump() for m in merchants],
        "transactions": [t.model_dump() for t in txns],
        "deliveries": [d.model_dump() for d in deliveries],
    }
    return ledger, cases


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ledger, cases = generate(args.seed)
    (out / "ledger.json").write_text(json.dumps(ledger, indent=1))
    (out / "cases.json").write_text(json.dumps([c.model_dump(mode="json") for c in cases], indent=1))
    print(f"wrote {len(cases)} cases, {len(ledger['transactions'])} transactions to {out}/")


if __name__ == "__main__":
    main()
