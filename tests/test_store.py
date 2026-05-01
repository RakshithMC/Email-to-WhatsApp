from pathlib import Path

from src.email_client import EmailItem
from src.store import ProcessedEmailStore


def test_store_marks_and_reads_processed_email(tmp_path: Path) -> None:
    db_path = tmp_path / "automation.db"
    store = ProcessedEmailStore(str(db_path))

    assert store.is_empty() is True
    assert store.has_processed("k1") is False
    store.mark_processed(
        dedupe_key="k1",
        provider="gmail",
        mailbox="INBOX",
        subject="Subject",
        sender_email="sender@example.com",
        received_at="2026-05-01 00:00:00 UTC",
    )
    assert store.is_empty() is False
    assert store.has_processed("k1") is True


def test_store_persists_due_pending_notifications(tmp_path: Path) -> None:
    db_path = tmp_path / "automation.db"
    store = ProcessedEmailStore(str(db_path))
    item = EmailItem(
        dedupe_key="retry-1",
        sender_name="Retry Sender",
        sender_email="retry@example.com",
        subject="Retry subject",
        received_at="2026-05-01 00:00:00 UTC",
        preview="Retry preview",
        has_attachments=False,
    )

    store.upsert_pending_notification(
        item=item,
        attempts=2,
        next_retry_at="2000-01-01 00:00:00",
        last_error="timeout",
    )

    due_items = store.get_due_pending_notifications()
    assert len(due_items) == 1
    due_item, attempts = due_items[0]
    assert due_item.dedupe_key == "retry-1"
    assert attempts == 2

    store.delete_pending_notification("retry-1")
    assert store.get_due_pending_notifications() == []
