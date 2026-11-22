import pytest

from fintech_audit_rl.generator.company import seeded_clean_kzt
from fintech_audit_rl.storage.public_store import PublicStore


def test_public_pages_and_documents_expose_only_public_data():
    company, metadata = seeded_clean_kzt(23)
    store = PublicStore(company)
    cursor = None
    seen = []
    while True:
        page = store.list_records("ledger", cursor, 2)
        seen.extend(page["records"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == company.manifest.ledger_count == 6
    assert len({row["row_id"] for row in seen}) == 6
    assert store.get_record("ledger", seen[0]["row_id"]) == seen[0]
    assert store.get_document(company.policy.doc_id)["doc_id"] == company.policy.doc_id
    assert str(metadata.seed) not in str(seen)
    assert "truth" not in str(seen)


def test_wrong_cursor_and_unknown_id_are_bounded_errors():
    company, _ = seeded_clean_kzt(24)
    store = PublicStore(company)
    for cursor in ("1", f"{company.manifest.episode_id}:payments:1", "x:ledger:0"):
        with pytest.raises(ValueError):
            store.list_records("ledger", cursor, 2)
    with pytest.raises(ValueError):
        store.get_record("ledger", "unknown")
    with pytest.raises(ValueError):
        store.get_document("unknown")
