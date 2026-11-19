"""Developer worker: public JSON messages only, without evaluator imports."""

import json
import random
import sys


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
