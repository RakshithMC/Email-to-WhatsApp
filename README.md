# Emails to WhatsApp Automation

This service polls your inbox every minute over IMAP and forwards each new email to WhatsApp through either the Twilio WhatsApp API or the Meta WhatsApp Cloud API.

It is designed for Gmail, Outlook, Yahoo, and custom IMAP inboxes without storing mailbox passwords in code. Credentials are loaded from environment variables, and Gmail/Yahoo should use app passwords.

## Features

- Supports Gmail, Outlook, Yahoo, and custom IMAP accounts
- Polls `INBOX` every 60 seconds
- Extracts sender name, sender email, subject, received time, and the first 300 characters
- Avoids duplicate alerts with SQLite-backed dedupe keys
- Retries failed WhatsApp sends automatically
- Keeps delivery logs in SQLite
- Supports optional VIP sender filtering, important-only filtering, and attachment alerts
- Supports `WHATSAPP_PROVIDER=twilio` or `WHATSAPP_PROVIDER=meta`

## Architecture

1. `src/main.py` runs an always-on worker loop.
2. `src/email_client.py` connects to IMAP, reads unread inbox emails, and builds message previews.
3. `src/notifier.py` sends formatted WhatsApp notifications through Twilio or Meta.
4. `src/store.py` stores processed messages and delivery logs in `data/automation.db`.

## WhatsApp Message Format

```text
\U0001F4E9 New Email Received

From: Sender Name (sender@example.com)
Subject: Subject line
Time: 2026-05-01 18:30:00 IST

Preview:
First 300 characters of the email body
```

## Prerequisites

- Python 3.11+
- A WhatsApp delivery backend: Twilio WhatsApp API or Meta WhatsApp Cloud API
- IMAP enabled on your mailbox

## Email Provider Setup

### Gmail

1. Enable IMAP in Gmail settings.
2. Turn on 2-Step Verification.
3. Create an App Password for Mail.
4. Set `EMAIL_PROVIDER=gmail`.

### Outlook

1. Make sure IMAP access is enabled for your mailbox.
2. Use your mailbox password or an app password if your tenant requires it.
3. Set `EMAIL_PROVIDER=outlook`.

### Yahoo

1. Enable IMAP access.
2. Create an app password in Yahoo Account Security.
3. Set `EMAIL_PROVIDER=yahoo`.

### Custom IMAP

1. Set `EMAIL_PROVIDER=imap`.
2. Provide `EMAIL_HOST`, `EMAIL_PORT`, and credentials.

## WhatsApp Setup

### Option 1: Twilio WhatsApp

1. Create a [Twilio account](https://www.twilio.com/try-twilio).
2. Enable the WhatsApp Sandbox or provision a WhatsApp-enabled sender.
3. Copy:
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `TWILIO_WHATSAPP_FROM`
4. Set `WHATSAPP_TO` to your own WhatsApp number in Twilio format, for example `whatsapp:+9198xxxxxxx`.
5. If using the sandbox, join the sandbox from your phone first.

### Option 2: Meta WhatsApp Cloud API

1. Create a Meta app in the [Meta for Developers](https://developers.facebook.com/) console.
2. Enable WhatsApp and create or connect a business phone number.
3. Copy:
   - `META_WHATSAPP_ACCESS_TOKEN`
   - `META_WHATSAPP_PHONE_NUMBER_ID`
4. Set `WHATSAPP_PROVIDER=meta`.
5. Set `WHATSAPP_TO` to your phone number, for example `+9198xxxxxxx` or `whatsapp:+9198xxxxxxx`.

## Local Setup

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill in the values in `.env`, then run:

```powershell
python -m src.main
```

Or on Windows, start it in the background with:

```powershell
.\start_worker.ps1
```

## Environment Variables

Required email settings:

- `EMAIL_PROVIDER`
- `EMAIL_USERNAME`
- `EMAIL_PASSWORD`

Required for `WHATSAPP_PROVIDER=twilio`:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WHATSAPP_FROM`
- `WHATSAPP_TO`
  - Must be in `whatsapp:+<countrycode><number>` format

Required for `WHATSAPP_PROVIDER=meta`:

- `META_WHATSAPP_ACCESS_TOKEN`
- `META_WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_TO`
  - Can be `+<countrycode><number>` or `whatsapp:+<countrycode><number>`

Optional:

- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_USE_SSL`
- `EMAIL_MAILBOX`
- `POLL_INTERVAL_SECONDS`
- `BODY_PREVIEW_LENGTH`
- `ONLY_UNREAD`
- `IMPORTANT_ONLY`
- `VIP_SENDERS`
- `INCLUDE_ATTACHMENTS_ALERT`
- `TZ`
- `DB_PATH`
- `LOG_LEVEL`
- `META_WHATSAPP_ACCESS_TOKEN`
- `META_WHATSAPP_PHONE_NUMBER_ID`

## Filters and Rules

- Spam and Promotions are skipped by polling only the `INBOX` mailbox.
- Duplicate alerts are prevented using a dedupe key based on provider, mailbox, and `Message-ID` or IMAP UID.
- Failed WhatsApp deliveries retry up to 3 times with exponential backoff.
- Delivery attempts are stored in the `delivery_logs` table.
- Startup validation fails fast if required provider credentials are missing or invalid.

## Deployment

### Render

Create a Background Worker service and configure:

- Build command: `pip install -r requirements.txt`
- Start command: `python -m src.main`

Add all `.env` variables in the Render dashboard.

Persist `data/automation.db` on a disk mount if you want duplicate suppression history to survive redeploys.

### Railway

1. Create a new service from this repo/folder.
2. Set the start command to `python -m src.main`.
3. Add the required environment variables.
4. Mount persistent storage if you want the SQLite database to survive redeploys.

### VPS / EC2

Run the service under `systemd` or `pm2` equivalent for Python. Example `systemd` service:

```ini
[Unit]
Description=Emails to WhatsApp
After=network.target

[Service]
WorkingDirectory=/opt/emails-to-whatsapp
ExecStart=/opt/emails-to-whatsapp/.venv/bin/python -m src.main
Restart=always
EnvironmentFile=/opt/emails-to-whatsapp/.env

[Install]
WantedBy=multi-user.target
```

## Logs and Data

- SQLite database: `data/automation.db`
- Delivery status rows: `delivery_logs`
- Processed email rows: `processed_emails`

## Security Notes

- Credentials are loaded only from environment variables.
- Do not commit `.env`.
- For Gmail and Yahoo, prefer app passwords.
- For enterprise mailboxes, use app passwords or provider-approved mailbox secrets.
- For Meta Cloud API, use a long-lived system user token in production.

## Advanced Features Included

- VIP sender filtering with `VIP_SENDERS`
- Important-only mode with `IMPORTANT_ONLY=true`
- Attachment indicator with `INCLUDE_ATTACHMENTS_ALERT=true`

## Docker Deployment

Build and run locally:

```powershell
docker build -t emails-to-whatsapp .
docker run --env-file .env emails-to-whatsapp
```

## Testing

Run the unit tests with:

```powershell
py -3 -m pytest -q
```
