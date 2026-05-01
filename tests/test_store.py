from pathlib import Path

from src.store import ProcessedEmailStore


def test_store_marks_and_reads_processed_email(tmp_path: Path) -> None:
    db_path = tmp_path / "automation.db"
    store = ProcessedEmailStore(str(db_path))

    assert store.has_processed("k1") is False
    store.mark_processed(
        dedupe_key="k1",
        provider="gmail",
        mailbox="INBOX",
        subject="Subject",
        sender_email="sender@example.com",
        received_at="2026-05-01 00:00:00 UTC",
    )
    assert store.has_processed("k1") is True
