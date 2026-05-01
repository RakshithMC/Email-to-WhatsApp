from src.email_client import ImapInboxClient


def test_idle_response_indicates_mailbox_change_for_exists() -> None:
    assert ImapInboxClient._response_indicates_mailbox_change("EXISTS", [b"5"]) is True


def test_idle_response_indicates_mailbox_change_for_recent() -> None:
    assert ImapInboxClient._response_indicates_mailbox_change(b"RECENT", [b"1"]) is True


def test_idle_response_ignores_non_mailbox_updates() -> None:
    assert ImapInboxClient._response_indicates_mailbox_change("OK", [b"still here"]) is False
