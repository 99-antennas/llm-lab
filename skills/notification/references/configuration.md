# Configuration

Configure one or both channels with environment variables.

## Channel Selection

- `APPROVAL_NOTIFY_CHANNEL`: `email`, `sms`, or `both` (default: `email`)

## Email (Google Workspace Gmail API)

- `APPROVAL_EMAIL_TO`: destination address
- `APPROVAL_EMAIL_FROM`: Google Workspace sender mailbox (for domain-wide delegated send)
- `GOOGLE_APPLICATION_CREDENTIALS`: service account JSON key path

The notifier also loads values from `config/master_config.yaml` using the
project config manager, where secret values are resolved via Google Secret
Manager (`gsm://...`).

## SMS (Twilio REST API)

- `TWILIO_ACCOUNT_SID`: account SID
- `TWILIO_AUTH_TOKEN`: auth token
- `TWILIO_FROM`: Twilio phone number in E.164 format
- `TWILIO_TO`: destination phone number in E.164 format

## Smoke Test

```bash
python3 scripts/send_notification.py \
  --reason "dry run test" \
  --command "echo test" \
  --workspace "/absolute/path" \
  --dry-run
```
