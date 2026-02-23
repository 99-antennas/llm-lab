# Google Secret Manager Setup Guide

This project uses Google Secret Manager for runtime secrets.

## 1. Create a GCP Project

1. Create/select a project in Google Cloud Console.
2. Enable Secret Manager API.

```bash
gcloud services enable secretmanager.googleapis.com --project "$GOOGLE_CLOUD_PROJECT"
```

## 2. Create Service Accounts (Simple Two-Account Model)

Create one service account for secrets access and one for app operations.

```bash
gcloud iam service-accounts create llm-lab-secrets \
  --display-name="LLM Lab Secrets"

gcloud iam service-accounts create llm-lab-app \
  --display-name="LLM Lab App"
```

Grant secret read access only to `llm-lab-secrets`:

```bash
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
  --member="serviceAccount:llm-lab-secrets@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"


## 3. Add a Basic Password Secret

Create a secret and set value:

```bash
printf 'test-password' | gcloud secrets create llm-lab-test-password \
  --data-file=- \
  --replication-policy="automatic" \
  --project "$GOOGLE_CLOUD_PROJECT"
```

If secret already exists, add a new version:

```bash
printf 'test-password-v2' | gcloud secrets versions add llm-lab-test-password \
  --data-file=- \
  --project "$GOOGLE_CLOUD_PROJECT"
```

## 4. Reference the Secret in Project Config

Use reference format:

- `gsm://<project>/<secret>/<version>`
- Example: `gsm://$GOOGLE_CLOUD_PROJECT/llm-lab-test-password/latest`

In `config/master_config.yaml`:

```yaml
notification:
  - name: smtp_password
    type: secret
    secret_ref: gsm://projects/$GOOGLE_CLOUD_PROJECT/secrets/llm-lab-test-password/versions/latest
```

## 5. Runtime Environment

Set required environment variables:

```bash
export GOOGLE_CLOUD_PROJECT="llm-lab-secrets"
export GOOGLE_APPLICATION_CREDENTIALS="/secure/path/llm-lab-secrets-sa.json"
```

If credentials are missing or invalid, client initialization and secret retrieval fail by design.

## 6. Twilio + Gmail Notification Prerequisites

### Twilio

Create GSM secrets for:

- `twilio-credentials` (single JSON payload)


JSON schema for `twilio-credentials`:

```json
{
  "account_sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "auth_token": "your_twilio_auth_token",
  "from_number": "+15550001111",
  "to_number": "+15550002222"
}
```

### Google Workspace Gmail API

1. Enable Gmail API in the same GCP project.
2. Use a service account key in `GOOGLE_APPLICATION_CREDENTIALS`.
3. Configure Google Workspace domain-wide delegation for the service account.
4. Set sender mailbox in profile config (`profile.email_from`, for example `alerts@99antennas.com`).

Then test notifications:

```bash
python3 skills/notification/scripts/send_notification.py \
  --reason "notification smoke test" \
  --command "echo test" \
  --workspace "/Users/kas/dev/llm-lab" \
  --channel both
```
