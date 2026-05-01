from __future__ import annotations

import email
import imaplib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime
from html import unescape
from typing import Iterable
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from src.config import EmailConfig


logger = logging.getLogger(__name__)
WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class EmailItem:
    dedupe_key: str
    sender_name: str
    sender_email: str
    subject: str
    received_at: str
    preview: str
    has_attachments: bool


class ImapInboxClient:
    def __init__(self, config: EmailConfig, timezone_name: str) -> None:
        self.config = config
        self.timezone = ZoneInfo(timezone_name)

    def fetch_new_messages(self) -> list[EmailItem]:
        client = self._connect()
        try:
            status, _ = client.select(self.config.mailbox, readonly=True)
            if status != "OK":
                raise RuntimeError(f"Failed to select mailbox {self.config.mailbox}")

            search_query = "UNSEEN" if self.config.only_unread else "ALL"
            status, data = client.uid("SEARCH", None, search_query)
            if status != "OK":
                raise RuntimeError("Failed to search mailbox")

            uids = [uid.decode("utf-8") for uid in data[0].split() if uid]
            items: list[EmailItem] = []
            for uid in uids:
                item = self._fetch_message(client, uid)
                if item and self._passes_filters(item):
                    items.append(item)
            return items
        finally:
            try:
                client.close()
            except Exception:
                pass
            client.logout()

    def _connect(self) -> imaplib.IMAP4_SSL | imaplib.IMAP4:
        if self.config.use_ssl:
            client = imaplib.IMAP4_SSL(self.config.host, self.config.port)
        else:
            client = imaplib.IMAP4(self.config.host, self.config.port)
        client.login(self.config.username, self.config.password)
        return client

    def _fetch_message(
        self, client: imaplib.IMAP4_SSL | imaplib.IMAP4, uid: str
    ) -> EmailItem | None:
        status, data = client.uid("FETCH", uid, "(RFC822)")
        if status != "OK" or not data or not data[0]:
            logger.warning("Unable to fetch message UID %s", uid)
            return None

        raw_message = data[0][1]
        message = email.message_from_bytes(raw_message)
        sender_name, sender_email = self._parse_sender(message)
        subject = self._decode_header_value(message.get("Subject", "(no subject)"))
        received_at = self._parse_received_at(message)
        preview = self._extract_preview(message)
        has_attachments = self._has_attachments(message)
        message_id = (message.get("Message-ID") or "").strip()
        dedupe_key = f"{self.config.provider}:{self.config.mailbox}:{message_id or uid}"

        return EmailItem(
            dedupe_key=dedupe_key,
            sender_name=sender_name,
            sender_email=sender_email,
            subject=subject,
            received_at=received_at,
            preview=preview,
            has_attachments=has_attachments,
        )

    def _parse_sender(self, message: Message) -> tuple[str, str]:
        addresses = getaddresses([message.get("From", "")])
        if not addresses:
            return "Unknown Sender", "unknown@example.com"
        raw_name, raw_email = addresses[0]
        sender_name = self._decode_header_value(raw_name) or raw_email or "Unknown Sender"
        return sender_name, raw_email or "unknown@example.com"

    def _parse_received_at(self, message: Message) -> str:
        date_header = message.get("Date")
        if not date_header:
            dt = datetime.now(tz=self.timezone)
        else:
            parsed = parsedate_to_datetime(date_header)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            dt = parsed.astimezone(self.timezone)
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")

    def _extract_preview(self, message: Message) -> str:
        text_parts: list[str] = []
        html_parts: list[str] = []

        if message.is_multipart():
            for part in message.walk():
                content_type = part.get_content_type()
                content_disposition = (part.get("Content-Disposition") or "").lower()
                if "attachment" in content_disposition:
                    continue
                payload = self._decode_part_payload(part)
                if not payload:
                    continue
                if content_type == "text/plain":
                    text_parts.append(payload)
                elif content_type == "text/html":
                    html_parts.append(payload)
        else:
            payload = self._decode_part_payload(message)
            if payload:
                if message.get_content_type() == "text/html":
                    html_parts.append(payload)
                else:
                    text_parts.append(payload)

        body = "\n".join(text_parts).strip()
        if not body and html_parts:
            combined_html = "\n".join(html_parts)
            body = BeautifulSoup(combined_html, "html.parser").get_text(separator=" ")

        clean = unescape(WHITESPACE_RE.sub(" ", body)).strip()
        if not clean:
            clean = "(No preview text available)"
        return clean[: self.config.body_preview_length]

    def _decode_part_payload(self, part: Message) -> str:
        payload = part.get_payload(decode=True)
        if payload is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace")
        except LookupError:
            return payload.decode("utf-8", errors="replace")

    def _has_attachments(self, message: Message) -> bool:
        if not message.is_multipart():
            return False
        for part in message.walk():
            disposition = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disposition:
                return True
        return False

    def _passes_filters(self, item: EmailItem) -> bool:
        if self.config.vip_senders:
            return item.sender_email.lower() in self.config.vip_senders
        if self.config.important_only:
            important_words = ("important", "urgent", "invoice", "payment", "otp")
            corpus = f"{item.subject} {item.preview}".lower()
            return any(word in corpus for word in important_words)
        return True

    @staticmethod
    def _decode_header_value(value: str) -> str:
        if not value:
            return ""
        try:
            return str(make_header(decode_header(value))).strip()
        except Exception:
            return value.strip()
