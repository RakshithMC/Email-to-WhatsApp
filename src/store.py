from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


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

    def has_processed(self, dedupe_key: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_emails WHERE dedupe_key = ?",
                (dedupe_key,),
            ).fetchone()
        return row is not None

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

