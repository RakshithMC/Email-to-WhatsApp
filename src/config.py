from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


PROVIDER_HOSTS = {
    "gmail": ("imap.gmail.com", 993),
    "outlook": ("outlook.office365.com", 993),
    "yahoo": ("imap.mail.yahoo.com", 993),
}

TIMEZONE_ALIASES = {
    "Asia/Calcutta": "Asia/Kolkata",
}


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


def _normalize_provider(provider: str) -> str:
    value = provider.strip().lower()
    if value not in {"gmail", "outlook", "yahoo", "imap"}:
        raise ValueError(
            "EMAIL_PROVIDER must be one of: gmail, outlook, yahoo, imap"
        )
    return value


@dataclass(frozen=True)
class EmailConfig:
    provider: str
    host: str
    port: int
    username: str
    password: str
    use_ssl: bool
    mailbox: str
    only_unread: bool
    important_only: bool
    vip_senders: tuple[str, ...]
    body_preview_length: int
    include_attachments_alert: bool


@dataclass(frozen=True)
class WhatsAppConfig:
    provider: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_from: str
    whatsapp_to: str
    meta_access_token: str
    meta_phone_number_id: str


@dataclass(frozen=True)
class AppConfig:
    email: EmailConfig
    whatsapp: WhatsAppConfig
    poll_interval_seconds: int
    log_level: str
    db_path: str
    timezone_name: str


def load_config() -> AppConfig:
    provider = _normalize_provider(os.getenv("EMAIL_PROVIDER", "gmail"))
    preset_host, preset_port = PROVIDER_HOSTS.get(provider, ("", 993))
    host = os.getenv("EMAIL_HOST") or preset_host
    port = _get_int("EMAIL_PORT", preset_port)
    username = os.getenv("EMAIL_USERNAME", "").strip()
    password = os.getenv("EMAIL_PASSWORD", "").strip()

    if not host:
        raise ValueError("EMAIL_HOST is required for custom IMAP accounts")
    if not username or not password:
        raise ValueError("EMAIL_USERNAME and EMAIL_PASSWORD are required")

    wa_provider = os.getenv("WHATSAPP_PROVIDER", "twilio").strip().lower()
    if wa_provider not in {"twilio", "meta"}:
        raise ValueError(
            "WHATSAPP_PROVIDER must be one of: twilio, meta"
        )

    vip_senders = tuple(
        item.strip().lower()
        for item in os.getenv("VIP_SENDERS", "").split(",")
        if item.strip()
    )

    timezone_name = os.getenv("TZ", "UTC").strip() or "UTC"
    timezone_name = TIMEZONE_ALIASES.get(timezone_name, timezone_name)

    config = AppConfig(
        email=EmailConfig(
            provider=provider,
            host=host,
            port=port,
            username=username,
            password=password,
            use_ssl=_get_bool("EMAIL_USE_SSL", True),
            mailbox=os.getenv("EMAIL_MAILBOX", "INBOX").strip() or "INBOX",
            only_unread=_get_bool("ONLY_UNREAD", True),
            important_only=_get_bool("IMPORTANT_ONLY", False),
            vip_senders=vip_senders,
            body_preview_length=_get_int("BODY_PREVIEW_LENGTH", 300),
            include_attachments_alert=_get_bool("INCLUDE_ATTACHMENTS_ALERT", True),
        ),
        whatsapp=WhatsAppConfig(
            provider=wa_provider,
            twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID", "").strip(),
            twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN", "").strip(),
            twilio_whatsapp_from=os.getenv("TWILIO_WHATSAPP_FROM", "").strip(),
            whatsapp_to=os.getenv("WHATSAPP_TO", "").strip(),
            meta_access_token=os.getenv("META_WHATSAPP_ACCESS_TOKEN", "").strip(),
            meta_phone_number_id=os.getenv("META_WHATSAPP_PHONE_NUMBER_ID", "").strip(),
        ),
        poll_interval_seconds=_get_int("POLL_INTERVAL_SECONDS", 60),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        db_path=os.getenv("DB_PATH", "data/automation.db").strip(),
        timezone_name=timezone_name,
    )
    _validate_config(config)
    return config


def _validate_config(config: AppConfig) -> None:
    if config.email.port <= 0:
        raise ValueError("EMAIL_PORT must be a positive integer")
    if config.poll_interval_seconds <= 0:
        raise ValueError("POLL_INTERVAL_SECONDS must be a positive integer")
    if config.email.body_preview_length <= 0:
        raise ValueError("BODY_PREVIEW_LENGTH must be a positive integer")
    if not config.db_path:
        raise ValueError("DB_PATH is required")

    wa = config.whatsapp
    if not wa.whatsapp_to:
        raise ValueError("WHATSAPP_TO is required")

    if wa.provider == "twilio":
        missing = [
            name
            for name, value in {
                "TWILIO_ACCOUNT_SID": wa.twilio_account_sid,
                "TWILIO_AUTH_TOKEN": wa.twilio_auth_token,
                "TWILIO_WHATSAPP_FROM": wa.twilio_whatsapp_from,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(
                f"Missing Twilio WhatsApp settings: {', '.join(missing)}"
            )
        if not wa.whatsapp_to.startswith("whatsapp:"):
            raise ValueError("WHATSAPP_TO must start with whatsapp: for Twilio")

    if wa.provider == "meta":
        missing = [
            name
            for name, value in {
                "META_WHATSAPP_ACCESS_TOKEN": wa.meta_access_token,
                "META_WHATSAPP_PHONE_NUMBER_ID": wa.meta_phone_number_id,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(
                f"Missing Meta WhatsApp settings: {', '.join(missing)}"
            )
