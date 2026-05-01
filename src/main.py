from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from src.config import load_config
from src.email_client import EmailItem
from src.email_client import ImapInboxClient
from src.notifier import build_notifier
from src.store import ProcessedEmailStore


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def _schedule_retry(attempts: int, delay_seconds: int) -> str:
    retry_at = datetime.now(timezone.utc) + timedelta(
        seconds=delay_seconds * max(attempts, 1)
    )
    return retry_at.strftime("%Y-%m-%d %H:%M:%S")


def _send_item(
    item: EmailItem,
    config: Any,
    store: ProcessedEmailStore,
    notifier: Any,
    logger: logging.Logger,
    prior_attempts: int = 0,
) -> None:
    try:
        provider_message_id = notifier.send(
            item,
            include_attachments_alert=config.email.include_attachments_alert,
        )
        store.mark_processed(
            dedupe_key=item.dedupe_key,
            provider=config.email.provider,
            mailbox=config.email.mailbox,
            subject=item.subject,
            sender_email=item.sender_email,
            received_at=item.received_at,
        )
        store.delete_pending_notification(item.dedupe_key)
        store.log_delivery(
            dedupe_key=item.dedupe_key,
            status="sent",
            provider_message_id=provider_message_id,
        )
    except Exception as exc:
        attempts = prior_attempts + 1
        logger.exception("Failed to notify for %s", item.dedupe_key)
        store.log_delivery(
            dedupe_key=item.dedupe_key,
            status="failed",
            error_message=str(exc),
        )
        if attempts >= config.failed_retry_max_attempts:
            logger.error(
                "Giving up on %s after %s total failed delivery attempt(s)",
                item.dedupe_key,
                attempts,
            )
            return
        store.upsert_pending_notification(
            item=item,
            attempts=attempts,
            next_retry_at=_schedule_retry(
                attempts=attempts,
                delay_seconds=config.failed_retry_delay_seconds,
            ),
            last_error=str(exc),
        )


def run() -> None:
    config = load_config()
    configure_logging(config.log_level)
    logger = logging.getLogger("emails_to_whatsapp")

    store = ProcessedEmailStore(config.db_path)
    inbox = ImapInboxClient(config.email, config.timezone_name)
    notifier = build_notifier(config)

    if config.skip_existing_on_startup and store.is_empty():
        seed_count = 0
        try:
            existing_messages = inbox.fetch_new_messages()
            for item in existing_messages:
                store.mark_processed(
                    dedupe_key=item.dedupe_key,
                    provider=config.email.provider,
                    mailbox=config.email.mailbox,
                    subject=item.subject,
                    sender_email=item.sender_email,
                    received_at=item.received_at,
                )
            seed_count = len(existing_messages)
        except Exception:
            logger.exception("Initial inbox seeding failed")
        else:
            logger.info(
                "Seeded %s existing unread email(s) to avoid first-run backfill",
                seed_count,
            )

    logger.info(
        "Email to WhatsApp worker started for provider=%s mailbox=%s mode=imap-idle idle_timeout=%ss retry_check=%ss",
        config.email.provider,
        config.email.mailbox,
        config.idle_timeout_seconds,
        config.poll_interval_seconds,
    )

    try:
        while True:
            try:
                _process_due_retries(config, store, notifier, logger)
                _process_new_messages(config, store, inbox, notifier, logger)

                mailbox_changed = inbox.wait_for_mailbox_update(
                    timeout_seconds=min(
                        config.idle_timeout_seconds,
                        config.poll_interval_seconds,
                    )
                )
                if mailbox_changed:
                    logger.info("IMAP IDLE detected mailbox change")
            except Exception:
                logger.exception("Real-time inbox loop failed; reconnecting soon")
                inbox.close()
                time.sleep(min(config.poll_interval_seconds, 10))
    finally:
        inbox.close()


def _process_due_retries(
    config: Any,
    store: ProcessedEmailStore,
    notifier: Any,
    logger: logging.Logger,
) -> None:
    for item, attempts in store.get_due_pending_notifications():
        logger.info(
            "Retrying pending notification for %s after %s failed attempt(s)",
            item.dedupe_key,
            attempts,
        )
        _send_item(
            item=item,
            config=config,
            store=store,
            notifier=notifier,
            logger=logger,
            prior_attempts=attempts,
        )


def _process_new_messages(
    config: Any,
    store: ProcessedEmailStore,
    inbox: ImapInboxClient,
    notifier: Any,
    logger: logging.Logger,
) -> None:
    messages = inbox.fetch_new_messages()
    logger.info("Fetched %s candidate email(s)", len(messages))
    for item in messages:
        if store.has_processed(item.dedupe_key):
            logger.info("Skipping duplicate email %s", item.dedupe_key)
            continue

        _send_item(
            item=item,
            config=config,
            store=store,
            notifier=notifier,
            logger=logger,
        )


if __name__ == "__main__":
    run()
