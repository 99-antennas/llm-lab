# Configuration

Configure one or both channels with environment variables.

## Channel Selection

- `APPROVAL_NOTIFY_CHANNEL`: `email`, `sms`, or `both` (default: `email`)

## Email (Google Workspace Gmail API)

- `profile.email_to` in `config/master_config.yaml`: destination address
- `profile.email_from` in `config/master_config.yaml`: Google Workspace sender mailbox
- `GOOGLE_CLOUD_KEYFILE`: service account JSON key path

The notifier also loads values from `config/master_config.yaml` using the
project config manager, where secret values are resolved via Google Secret
Manager (`gsm://...`).

## SMS (Twilio REST API)

- `notification.twilio_credentials` in `config/master_config.yaml` (secret): JSON payload with
  `account_sid`, `auth_token`, `from_number`
- `profile.to_number` in `config/master_config.yaml`: destination phone number in E.164 format

## Smoke Test

```bash
python3 scripts/send_notification.py \
  --reason "dry run test" \
  --command "echo test" \
  --workspace "/absolute/path" \
  --dry-run
```
