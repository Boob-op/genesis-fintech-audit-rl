"""Developer worker: public JSON messages only, without evaluator imports."""

import json
import sys


def ask(action: dict) -> dict:
    print(json.dumps({"action": action}, separators=(",", ":")), flush=True)
    reply = json.loads(sys.stdin.readline())
    return reply["observation"]


def main() -> int:
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
    invoice_rows = {}
    for row in records:
        if row["role"] == "invoice_recognition":
            invoice_rows.setdefault(row["invoice_id"], []).append(row)
    findings = []
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
                "evidence_ids": [invoice["doc_id"], *[row["row_id"] for row in rows], policy_id],
                "explanation": "Invoice recognition exceeds the genuine invoice amount.",
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
