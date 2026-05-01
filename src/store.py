from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from src.email_client import EmailItem


class ProcessedEmailStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_emails (
                    dedupe_key TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    mailbox TEXT NOT NULL,
                    subject TEXT,
                    sender_email TEXT,
                    received_at TEXT,
                    processed_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS delivery_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dedupe_key TEXT NOT NULL,
                    status TEXT NOT NULL,
                    provider_message_id TEXT,
                    error_message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_notifications (
                    dedupe_key TEXT PRIMARY KEY,
                    sender_name TEXT NOT NULL,
                    sender_email TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    preview TEXT NOT NULL,
                    has_attachments INTEGER NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_retry_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_error TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def has_processed(self, dedupe_key: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_emails WHERE dedupe_key = ?",
                (dedupe_key,),
            ).fetchone()
        return row is not None

    def is_empty(self) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM processed_emails LIMIT 1").fetchone()
        return row is None

    def mark_processed(
        self,
        dedupe_key: str,
        provider: str,
        mailbox: str,
        subject: str,
        sender_email: str,
        received_at: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO processed_emails
                (dedupe_key, provider, mailbox, subject, sender_email, received_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (dedupe_key, provider, mailbox, subject, sender_email, received_at),
            )

    def log_delivery(
        self,
        dedupe_key: str,
        status: str,
        provider_message_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO delivery_logs
                (dedupe_key, status, provider_message_id, error_message)
                VALUES (?, ?, ?, ?)
                """,
                (dedupe_key, status, provider_message_id, error_message),
            )

    def upsert_pending_notification(
        self,
        item: EmailItem,
        attempts: int,
        next_retry_at: str,
        last_error: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO pending_notifications (
                    dedupe_key,
                    sender_name,
                    sender_email,
                    subject,
                    received_at,
                    preview,
                    has_attachments,
                    attempts,
                    next_retry_at,
                    last_error,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(dedupe_key) DO UPDATE SET
                    sender_name = excluded.sender_name,
                    sender_email = excluded.sender_email,
                    subject = excluded.subject,
                    received_at = excluded.received_at,
                    preview = excluded.preview,
                    has_attachments = excluded.has_attachments,
                    attempts = excluded.attempts,
                    next_retry_at = excluded.next_retry_at,
                    last_error = excluded.last_error,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    item.dedupe_key,
                    item.sender_name,
                    item.sender_email,
                    item.subject,
                    item.received_at,
                    item.preview,
                    int(item.has_attachments),
                    attempts,
                    next_retry_at,
                    last_error,
                ),
            )

    def get_due_pending_notifications(self, limit: int = 100) -> list[tuple[EmailItem, int]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    dedupe_key,
                    sender_name,
                    sender_email,
                    subject,
                    received_at,
                    preview,
                    has_attachments,
                    attempts
                FROM pending_notifications
                WHERE next_retry_at <= CURRENT_TIMESTAMP
                ORDER BY next_retry_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            (
                EmailItem(
                    dedupe_key=row[0],
                    sender_name=row[1],
                    sender_email=row[2],
                    subject=row[3],
                    received_at=row[4],
                    preview=row[5],
                    has_attachments=bool(row[6]),
                ),
                row[7],
            )
            for row in rows
        ]

    def delete_pending_notification(self, dedupe_key: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM pending_notifications WHERE dedupe_key = ?",
                (dedupe_key,),
            )
