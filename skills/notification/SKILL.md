---
name: notification
description: Send SMS via Twilio or email via Google Workspace Gmail API before approval prompts.
---

# Notification

Use this skill when an operation requires user approval and the user asked to be notified by text or email.

## Setup

1. Read `references/configuration.md`.
2. Confirm channel configuration exists in environment variables.
3. Prefer `APPROVAL_NOTIFY_CHANNEL` to select default channel (`email`, `sms`, or `both`).

## Workflow

1. Detect that a command will require `sandbox_permissions="require_escalated"`.
2. Build a short reason string and include the exact command that needs approval.
3. Run:

```bash
python3 scripts/send_notification.py \
  --reason "<why approval is required>" \
  --command "<exact command>" \
  --workspace "<absolute workspace path>"
```

4. If alerting fails, continue with the normal approval request and mention that notification failed.
5. If alerting succeeds, proceed with the normal approval request flow.

## Guardrails

- Never include secrets in alert messages.
- Keep alert bodies short and actionable.
- Use `--dry-run` first when testing configuration changes.
