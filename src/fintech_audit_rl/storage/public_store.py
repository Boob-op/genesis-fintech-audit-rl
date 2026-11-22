"""Read-only in-memory public records for the first episode."""

from typing import Protocol

from fintech_audit_rl.schemas.public import (
    FxRow,
    Invoice,
    LedgerRow,
    Manifest,
    Payment,
    Policy,
    fx_evidence_id,
)


class PublicBundle(Protocol):
    manifest: Manifest
    policy: Policy
    invoices: tuple[Invoice, ...]
    payments: tuple[Payment, ...]
    ledger: tuple[LedgerRow, ...]
    fx: tuple[FxRow, ...]


class PublicStore:
    def __init__(self, company: PublicBundle):
        self.manifest = company.manifest
        self.policy = company.policy
        self._tables = {
            "ledger": tuple(row.model_dump(mode="json") for row in company.ledger),
            "invoices": tuple(doc.model_dump(mode="json") for doc in company.invoices),
            "payments": tuple(doc.model_dump(mode="json") for doc in company.payments),
            "fx": tuple(
                {
                    "id": fx_evidence_id(company.manifest.episode_id, row),
                    **row.model_dump(mode="json"),
                }
                for row in company.fx
            ),
        }
        self._documents = {
            company.policy.doc_id: company.policy.model_dump(mode="json"),
            **{
                doc.doc_id: doc.model_dump(mode="json")
                for doc in (*company.invoices, *company.payments)
            },
        }
        self._index = {}
        for table, records in self._tables.items():
            field = {"ledger": "row_id", "invoices": "doc_id", "payments": "doc_id", "fx": "id"}[
                table
            ]
            self._index[table] = {record[field]: record for record in records}

    def list_records(self, table: str, cursor: str | None, limit: int) -> dict:
        if table not in self._tables or type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("invalid public query")
        if cursor is None:
            start = 0
        else:
            try:
                parts = cursor.split(":")
                if len(parts) != 3 or parts[:2] != [self.manifest.episode_id, table]:
                    raise ValueError
                start = int(parts[2])
            except (AttributeError, ValueError) as error:
                raise ValueError("invalid cursor") from error
        records = self._tables[table]
        if not 0 <= start <= len(records):
            raise ValueError("invalid cursor")
        end = min(start + limit, len(records))
        return {
            "records": list(records[start:end]),
            "next_cursor": (
                f"{self.manifest.episode_id}:{table}:{end}" if end < len(records) else None
            ),
        }

    def get_record(self, table: str, record_id: str) -> dict:
        if table not in self._index or record_id not in self._index[table]:
            raise ValueError("record not found")
        return dict(self._index[table][record_id])

    def get_document(self, doc_id: str) -> dict:
        if doc_id not in self._documents:
            raise ValueError("document not found")
        return dict(self._documents[doc_id])

    @property
    def public_ids(self) -> set[str]:
        return set(self._documents) | {key for table in self._index.values() for key in table}
