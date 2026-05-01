from __future__ import annotations

import logging
import time

import requests

from src.config import AppConfig
from src.email_client import EmailItem


logger = logging.getLogger(__name__)
EMAIL_ALERT_HEADER = "\U0001F4E9 New Email Received"


class WhatsAppNotifier:
    def send(self, item: EmailItem, include_attachments_alert: bool) -> str:
        raise NotImplementedError


class TwilioWhatsAppNotifier(WhatsAppNotifier):
    def __init__(self, config: AppConfig) -> None:
        wa = config.whatsapp
        missing = [
            name
            for name, value in {
                "TWILIO_ACCOUNT_SID": wa.twilio_account_sid,
                "TWILIO_AUTH_TOKEN": wa.twilio_auth_token,
                "TWILIO_WHATSAPP_FROM": wa.twilio_whatsapp_from,
                "WHATSAPP_TO": wa.whatsapp_to,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing Twilio WhatsApp settings: {', '.join(missing)}")

        self.account_sid = wa.twilio_account_sid
        self.auth_token = wa.twilio_auth_token
        self.from_number = wa.twilio_whatsapp_from
        self.to_number = wa.whatsapp_to

    def send(self, item: EmailItem, include_attachments_alert: bool) -> str:
        message = self._format_message(item, include_attachments_alert)
        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{self.account_sid}/Messages.json"
        )
        payload = {
            "From": self.from_number,
            "To": self.to_number,
            "Body": message,
        }

        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = requests.post(
                    url,
                    data=payload,
                    auth=(self.account_sid, self.auth_token),
                    timeout=20,
                )
                response.raise_for_status()
                data = response.json()
                sid = data.get("sid", "")
                logger.info("WhatsApp message sent for %s", item.dedupe_key)
                return sid
            except Exception as exc:
                last_error = exc
                logger.warning("WhatsApp send failed on attempt %s: %s", attempt, exc)
                if attempt < 3:
                    time.sleep(2**attempt)
        raise RuntimeError(f"Twilio send failed after retries: {last_error}") from last_error

    def _format_message(self, item: EmailItem, include_attachments_alert: bool) -> str:
        lines = [
            EMAIL_ALERT_HEADER,
            "",
            f"From: {item.sender_name} ({item.sender_email})",
            f"Subject: {item.subject}",
            f"Time: {item.received_at}",
        ]
        if include_attachments_alert and item.has_attachments:
            lines.append("Attachments: Yes")
        lines.extend(["", "Preview:", item.preview])
        return "\n".join(lines)


class MetaWhatsAppNotifier(WhatsAppNotifier):
    def __init__(self, config: AppConfig) -> None:
        wa = config.whatsapp
        missing = [
            name
            for name, value in {
                "META_WHATSAPP_ACCESS_TOKEN": wa.meta_access_token,
                "META_WHATSAPP_PHONE_NUMBER_ID": wa.meta_phone_number_id,
                "WHATSAPP_TO": wa.whatsapp_to,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing Meta WhatsApp settings: {', '.join(missing)}")

        self.access_token = wa.meta_access_token
        self.phone_number_id = wa.meta_phone_number_id
        self.to_number = wa.whatsapp_to.removeprefix("whatsapp:")

    def send(self, item: EmailItem, include_attachments_alert: bool) -> str:
        url = f"https://graph.facebook.com/v22.0/{self.phone_number_id}/messages"
        preview = item.preview
        if include_attachments_alert and item.has_attachments:
            preview = f"{preview}\n\nAttachments: Yes"

        body_text = (
            f"{EMAIL_ALERT_HEADER}\n\n"
            f"From: {item.sender_name} ({item.sender_email})\n"
            f"Subject: {item.subject}\n"
            f"Time: {item.received_at}\n\n"
            f"Preview:\n{preview}"
        )

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self.to_number.lstrip("+"),
            "type": "text",
            "text": {
                "preview_url": False,
                "body": body_text,
            },
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=20)
                response.raise_for_status()
                data = response.json()
                messages = data.get("messages") or []
                message_id = messages[0].get("id", "") if messages else ""
                logger.info("Meta WhatsApp message sent for %s", item.dedupe_key)
                return message_id
            except Exception as exc:
                last_error = exc
                logger.warning("Meta WhatsApp send failed on attempt %s: %s", attempt, exc)
                if attempt < 3:
                    time.sleep(2**attempt)
        raise RuntimeError(f"Meta send failed after retries: {last_error}") from last_error


def build_notifier(config: AppConfig) -> WhatsAppNotifier:
    if config.whatsapp.provider == "meta":
        return MetaWhatsAppNotifier(config)
    return TwilioWhatsAppNotifier(config)
