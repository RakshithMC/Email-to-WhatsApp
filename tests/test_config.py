import os

import pytest

from src.config import load_config


def _base_env() -> dict[str, str]:
    return {
        "EMAIL_PROVIDER": "gmail",
        "EMAIL_USERNAME": "user@example.com",
        "EMAIL_PASSWORD": "secret",
        "WHATSAPP_PROVIDER": "twilio",
        "TWILIO_ACCOUNT_SID": "sid",
        "TWILIO_AUTH_TOKEN": "token",
        "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886",
        "WHATSAPP_TO": "whatsapp:+911234567890",
        "DB_PATH": "data/test.db",
    }


def test_load_config_requires_twilio_whatsapp_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith(("EMAIL_", "WHATSAPP_", "TWILIO_", "META_", "DB_PATH", "POLL_", "BODY_")):
            monkeypatch.delenv(key, raising=False)
    for key, value in _base_env().items():
        monkeypatch.setenv(key, value)

    monkeypatch.setenv("WHATSAPP_TO", "+911234567890")

    with pytest.raises(ValueError, match="WHATSAPP_TO must start with whatsapp: for Twilio"):
        load_config()


def test_load_config_requires_positive_poll_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith(("EMAIL_", "WHATSAPP_", "TWILIO_", "META_", "DB_PATH", "POLL_", "BODY_")):
            monkeypatch.delenv(key, raising=False)
    for key, value in _base_env().items():
        monkeypatch.setenv(key, value)

    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "0")

    with pytest.raises(ValueError, match="POLL_INTERVAL_SECONDS must be a positive integer"):
        load_config()


def test_load_config_accepts_meta_recipient_without_whatsapp_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in list(os.environ):
        if key.startswith(("EMAIL_", "WHATSAPP_", "TWILIO_", "META_", "DB_PATH", "POLL_", "BODY_")):
            monkeypatch.delenv(key, raising=False)
    for key, value in _base_env().items():
        monkeypatch.setenv(key, value)

    monkeypatch.setenv("WHATSAPP_PROVIDER", "meta")
    monkeypatch.setenv("WHATSAPP_TO", "+911234567890")
    monkeypatch.setenv("META_WHATSAPP_ACCESS_TOKEN", "meta-token")
    monkeypatch.setenv("META_WHATSAPP_PHONE_NUMBER_ID", "12345")

    config = load_config()
    assert config.whatsapp.provider == "meta"


def test_load_config_defaults_skip_existing_on_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in list(os.environ):
        if key.startswith(("EMAIL_", "WHATSAPP_", "TWILIO_", "META_", "DB_PATH", "POLL_", "BODY_", "SKIP_")):
            monkeypatch.delenv(key, raising=False)
    for key, value in _base_env().items():
        monkeypatch.setenv(key, value)

    config = load_config()
    assert config.skip_existing_on_startup is True
    assert config.idle_timeout_seconds == 1740
    assert config.failed_retry_delay_seconds == 300
    assert config.failed_retry_max_attempts == 20


def test_load_config_requires_positive_failed_retry_delay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in list(os.environ):
        if key.startswith(("EMAIL_", "WHATSAPP_", "TWILIO_", "META_", "DB_PATH", "POLL_", "BODY_", "FAILED_")):
            monkeypatch.delenv(key, raising=False)
    for key, value in _base_env().items():
        monkeypatch.setenv(key, value)

    monkeypatch.setenv("FAILED_RETRY_DELAY_SECONDS", "0")

    with pytest.raises(ValueError, match="FAILED_RETRY_DELAY_SECONDS must be a positive integer"):
        load_config()


def test_load_config_requires_positive_idle_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in list(os.environ):
        if key.startswith(("EMAIL_", "WHATSAPP_", "TWILIO_", "META_", "DB_PATH", "POLL_", "BODY_", "IDLE_")):
            monkeypatch.delenv(key, raising=False)
    for key, value in _base_env().items():
        monkeypatch.setenv(key, value)

    monkeypatch.setenv("IDLE_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValueError, match="IDLE_TIMEOUT_SECONDS must be a positive integer"):
        load_config()
