"""Read-only tool layer over the synthetic ledger.

In a customer deployment this module is the only thing that changes: the same four
lookups get backed by the bank's core ledger, merchant master and logistics APIs.
The agent never sees raw tables, only these typed lookups.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Customer, Delivery, Dispute, Evidence, Merchant, Transaction


class Ledger:
    def __init__(
        self,
        customers: list[Customer],
        merchants: list[Merchant],
        transactions: list[Transaction],
        deliveries: list[Delivery],
    ) -> None:
        self._customers = {c.id: c for c in customers}
        self._merchants = {m.id: m for m in merchants}
        self._txns = {t.id: t for t in transactions}
        self._deliveries = {d.transaction_id: d for d in deliveries}

    @classmethod
    def from_file(cls, path: str | Path) -> Ledger:
        raw = json.loads(Path(path).read_text())
        return cls(
            customers=[Customer(**c) for c in raw["customers"]],
            merchants=[Merchant(**m) for m in raw["merchants"]],
            transactions=[Transaction(**t) for t in raw["transactions"]],
            deliveries=[Delivery(**d) for d in raw["deliveries"]],
        )

    # --- tools -----------------------------------------------------------

    def get_transaction(self, txn_id: str) -> Transaction:
        if txn_id not in self._txns:
            raise KeyError(f"unknown transaction {txn_id}")
        return self._txns[txn_id]

    def get_customer(self, customer_id: str) -> Customer:
        return self._customers[customer_id]

    def get_merchant(self, merchant_id: str) -> Merchant:
        return self._merchants[merchant_id]

    def related_transactions(self, txn: Transaction, window_days: int = 3) -> list[Transaction]:
        """Same customer, same merchant, within a few days. Used to spot duplicates."""
        from datetime import date

        d0 = date.fromisoformat(txn.date)
        out = []
        for t in self._txns.values():
            if t.id == txn.id or t.customer_id != txn.customer_id or t.merchant_id != txn.merchant_id:
                continue
            if abs((date.fromisoformat(t.date) - d0).days) <= window_days:
                out.append(t)
        return sorted(out, key=lambda t: (t.date, t.id))

    def get_delivery(self, txn_id: str) -> Delivery | None:
        return self._deliveries.get(txn_id)

    # --- convenience -----------------------------------------------------

    def gather(self, dispute: Dispute) -> Evidence:
        txn = self.get_transaction(dispute.transaction_id)
        return Evidence(
            dispute=dispute,
            customer=self.get_customer(dispute.customer_id),
            transaction=txn,
            merchant=self.get_merchant(txn.merchant_id),
            related_transactions=self.related_transactions(txn),
            delivery=self.get_delivery(txn.id),
        )
