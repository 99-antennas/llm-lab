# Google Auth + Project + Secret Manager Setup

Use these commands to authenticate, create the `llm-lab` project, and enable Secret Manager.

```bash
# 0) Install/initialize gcloud CLI first if needed:
# https://cloud.google.com/sdk/docs/install

# 1) Authenticate to Google (user auth for setup)
gcloud auth login

# (Optional) also set up ADC for local SDK-based tooling
gcloud auth application-default login

# 2) Create a new project named "llm-lab"
# NOTE: GOOGLE_CLOUD_PROJECT must be globally unique. Pick one like:
export GOOGLE_CLOUD_PROJECT="llm-lab-$(date +%s)"
export GOOGLE_CLOUD_PROJECT_NAME="llm-lab"

gcloud projects create "$GOOGLE_CLOUD_PROJECT" --name="$GOOGLE_CLOUD_PROJECT_NAME"

# Set it as active project
gcloud config set project "$GOOGLE_CLOUD_PROJECT"

# If prompted, link billing (required for most APIs)
# List billing accounts:
gcloud billing accounts list
# Link billing account:
# gcloud billing projects link "$GOOGLE_CLOUD_PROJECT" --billing-account=XXXXXX-XXXXXX-XXXXXX

# 3) Enable Secret Manager API in the project
gcloud services enable secretmanager.googleapis.com --project "$GOOGLE_CLOUD_PROJECT"

# Verify
gcloud services list --enabled --project "$GOOGLE_CLOUD_PROJECT" | grep secretmanager
```

## Service Accounts (Recommended Simple Model)

```bash
# Secrets-only service account
gcloud iam service-accounts create llm-lab-secrets \
  --display-name="LLM Lab Secrets"

# App operations service account
gcloud iam service-accounts create llm-lab-app \
  --display-name="LLM Lab App"

# Grant secret access to secrets account only
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
  --member="serviceAccount:llm-lab-secrets@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```
