from __future__ import annotations

import logging
import time

from src.config import load_config
from src.email_client import ImapInboxClient
from src.notifier import build_notifier
from src.store import ProcessedEmailStore


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def run() -> None:
    config = load_config()
    configure_logging(config.log_level)
    logger = logging.getLogger("emails_to_whatsapp")

    store = ProcessedEmailStore(config.db_path)
    inbox = ImapInboxClient(config.email, config.timezone_name)
    notifier = build_notifier(config)

    logger.info(
        "Email to WhatsApp worker started for provider=%s mailbox=%s interval=%ss",
        config.email.provider,
        config.email.mailbox,
        config.poll_interval_seconds,
    )

    while True:
        try:
            messages = inbox.fetch_new_messages()
            logger.info("Fetched %s candidate email(s)", len(messages))
            for item in messages:
                if store.has_processed(item.dedupe_key):
                    logger.info("Skipping duplicate email %s", item.dedupe_key)
                    continue

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
                    store.log_delivery(
                        dedupe_key=item.dedupe_key,
                        status="sent",
                        provider_message_id=provider_message_id,
                    )
                except Exception as exc:
                    logger.exception("Failed to notify for %s", item.dedupe_key)
                    store.log_delivery(
                        dedupe_key=item.dedupe_key,
                        status="failed",
                        error_message=str(exc),
                    )
        except Exception:
            logger.exception("Polling cycle failed")

        time.sleep(config.poll_interval_seconds)


if __name__ == "__main__":
    run()
