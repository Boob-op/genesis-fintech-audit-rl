"""Developer worker: public JSON messages only, without evaluator imports."""

import json
import random
import sys
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal

from fintech_audit_rl.schemas.public import policy_timezone


def ask(action: dict) -> dict:
    print(json.dumps({"action": action}, separators=(",", ":")), flush=True)
    reply = json.loads(sys.stdin.readline())
    return reply["observation"]


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "reconciliation"
    if mode not in {"reconciliation", "flag_all", "random_explorer"}:
        return 2
    initial = json.loads(sys.stdin.readline())
    manifest = initial["observation"]["manifest"]
    policy_id = manifest["policy_doc_id"]
    records = []
    cursor = None
    while True:
        observation = ask(
            {"type": "list_records", "table": "ledger", "cursor": cursor, "limit": 50}
        )
        records.extend(observation["records"])
        cursor = observation["next_cursor"]
        if cursor is None:
            break
    if mode == "random_explorer":
        policy_seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        rng = random.Random(policy_seed)
        for _ in range(8):
            if rng.randrange(2):
                ask({"type": "calculator", "expression": f"{rng.randrange(100)} + 1"})
            else:
                ask({"type": "get_record", "table": "ledger", "id": rng.choice(records)["row_id"]})
        ask(
            {
                "type": "submit",
                "submission": {
                    "episode_id": manifest["episode_id"],
                    "findings": [],
                },
            }
        )
        return 0
    findings = []
    if mode == "flag_all":
        for row in records[:30]:
            findings.append(
                {
                    "type": "duplicate_invoice",
                    "affected_ids": [row["row_id"]],
                    "claimed_amount_minor": row["debit_minor"] or row["credit_minor"],
                    "currency": manifest["base_currency"],
                    "evidence_ids": [row["row_id"], policy_id],
                    "explanation": "Flagged record.",
                }
            )
    else:
        invoice_rows = {}
        for row in records:
            if row["role"] == "invoice_recognition":
                invoice_rows.setdefault(row["invoice_id"], []).append(row)
        for invoice_id, rows in invoice_rows.items():
            entries = {row["entry_id"] for row in rows}
            if len(entries) < 2:
                continue
            invoice_docs = ask(
                {"type": "list_records", "table": "invoices", "cursor": None, "limit": 50}
            )["records"]
            invoice = next(item for item in invoice_docs if item["invoice_id"] == invoice_id)
            amount = sum(row["debit_minor"] for row in rows if row["account"] == "receivables")
            amount -= invoice["total_minor"]
            findings.append(
                {
                    "type": "duplicate_invoice",
                    "affected_ids": [row["row_id"] for row in rows],
                    "claimed_amount_minor": amount,
                    "currency": manifest["base_currency"],
                    "evidence_ids": [
                        invoice["doc_id"],
                        *[row["row_id"] for row in rows],
                        policy_id,
                    ],
                    "explanation": "Invoice recognition exceeds the genuine invoice amount.",
                }
            )
        payment_docs = ask(
            {"type": "list_records", "table": "payments", "cursor": None, "limit": 50}
        )["records"]
        invoice_docs = ask(
            {"type": "list_records", "table": "invoices", "cursor": None, "limit": 50}
        )["records"]
        invoice_by_id = {doc["invoice_id"]: doc for doc in invoice_docs}
        fx_records = ask({"type": "list_records", "table": "fx", "cursor": None, "limit": 50})[
            "records"
        ]
        for payment in payment_docs:
            for ref in payment["invoice_refs"]:
                invoice = invoice_by_id[ref["invoice_id"]]
                credits = [
                    row
                    for row in records
                    if row["role"] == "payment_allocation"
                    and row["payment_id"] == payment["payment_id"]
                    and row["invoice_id"] == ref["invoice_id"]
                    and row["account"] == "receivables"
                    and row["credit_minor"] > 0
                ]
                allocated = sum(row["allocated_source_minor"] for row in credits)
                if allocated < ref["amount_minor"]:
                    findings.append(
                        {
                            "type": "partial_allocation",
                            "affected_ids": [payment["doc_id"], invoice["doc_id"]],
                            "claimed_amount_minor": ref["amount_minor"] - allocated,
                            "currency": payment["currency"],
                            "evidence_ids": [
                                payment["doc_id"],
                                invoice["doc_id"],
                                policy_id,
                                *[row["row_id"] for row in credits],
                            ],
                            "explanation": "Recorded allocation is below the payment instruction.",
                        }
                    )
        public_policy = initial["observation"]["policy"]
        for payment in payment_docs:
            if payment["currency"] == manifest["base_currency"]:
                continue
            local_date = (
                datetime.fromisoformat(payment["timestamp"])
                .astimezone(policy_timezone(public_policy["timezone"]))
                .date()
                .isoformat()
            )
            reference = next(
                row
                for row in fx_records
                if row["date"] == local_date
                and row["source_currency"] == payment["currency"]
                and row["target_currency"] == manifest["base_currency"]
            )
            source_exp = public_policy["currency_exponents"][payment["currency"]]
            base_exp = public_policy["currency_exponents"][manifest["base_currency"]]
            expected = int(
                (
                    Decimal(payment["amount_minor"])
                    * Decimal(reference["rate"])
                    * Decimal(10) ** (base_exp - source_exp)
                ).quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
            )
            receipt = [
                row
                for row in records
                if row["role"] == "payment_receipt" and row["payment_id"] == payment["payment_id"]
            ]
            bank = next(row for row in receipt if row["account"] == "bank")
            wrong = bank["debit_minor"] != expected or any(
                row["fx_date"] != local_date or row["fx_rate"] != reference["rate"]
                for row in receipt
            )
            if wrong:
                findings.append(
                    {
                        "type": "fx_date_or_rate",
                        "affected_ids": [row["row_id"] for row in receipt],
                        "claimed_amount_minor": abs(bank["debit_minor"] - expected),
                        "currency": manifest["base_currency"],
                        "evidence_ids": [
                            payment["doc_id"],
                            *[row["row_id"] for row in receipt],
                            policy_id,
                            reference["id"],
                        ],
                        "explanation": "Receipt uses a wrong FX date or rate.",
                    }
                )
    ask(
        {
            "type": "submit",
            "submission": {
                "episode_id": manifest["episode_id"],
                "findings": findings,
            },
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
