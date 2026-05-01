from src.config import AppConfig, EmailConfig, WhatsAppConfig
from src.email_client import EmailItem
from src.notifier import MetaWhatsAppNotifier, TwilioWhatsAppNotifier


def _build_config(provider: str) -> AppConfig:
    return AppConfig(
        email=EmailConfig(
            provider="gmail",
            host="imap.gmail.com",
            port=993,
            username="user@example.com",
            password="secret",
            use_ssl=True,
            mailbox="INBOX",
            only_unread=True,
            important_only=False,
            vip_senders=(),
            body_preview_length=300,
            include_attachments_alert=True,
        ),
        whatsapp=WhatsAppConfig(
            provider=provider,
            twilio_account_sid="sid",
            twilio_auth_token="token",
            twilio_whatsapp_from="whatsapp:+14155238886",
            whatsapp_to="whatsapp:+911234567890",
            meta_access_token="meta-token",
            meta_phone_number_id="12345",
        ),
        poll_interval_seconds=60,
        idle_timeout_seconds=1740,
        skip_existing_on_startup=True,
        failed_retry_delay_seconds=300,
        failed_retry_max_attempts=20,
        log_level="INFO",
        db_path="data/test.db",
        timezone_name="UTC",
    )


def _build_item() -> EmailItem:
    return EmailItem(
        dedupe_key="test-key",
        sender_name="Example Sender",
        sender_email="sender@example.com",
        subject="Status Update",
        received_at="2026-05-01 19:00:00 UTC",
        preview="This is a test preview",
        has_attachments=True,
    )


def test_twilio_message_format_includes_attachment_marker() -> None:
    notifier = TwilioWhatsAppNotifier(_build_config("twilio"))
    body = notifier._format_message(_build_item(), include_attachments_alert=True)
    assert "New Email Received" in body
    assert "Attachments: Yes" in body


def test_meta_notifier_normalizes_recipient_number() -> None:
    notifier = MetaWhatsAppNotifier(_build_config("meta"))
    assert notifier.to_number == "+911234567890"
