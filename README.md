# LLM Lab
https://github.com/99-antennas/llm-lab/blob/main/README.md (public)

A self-hosted AI agent stack for an always-on local machine. It pairs a host-run llama.cpp model server with a FastAPI backend, Postgres, Open WebUI, and a file parsing pipeline.

# Requirements
- [llama.cpp](https://github.com/ggml-org/llama.cpp) — runs local LLMs natively on the host (Metal GPU on Apple Silicon)
- [huggingface_hub CLI](https://huggingface.co/docs/huggingface_hub/guides/cli) — downloads GGUF model files via `hf`
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — runs Postgres, API, Open WebUI, Pipelines
- [uv](https://github.com/astral-sh/uv) — Python package manager

## Host Python dependencies

Run `uv sync --locked` from this checkout to install host-side dependencies.
Hermes runs in its own Docker image and is not installed into the host Python
environment.

On macOS, if uv rejects ARM64 wheels while reporting a
`macosx_10_16_universal2` target, check for `SYSTEM_VERSION_COMPAT=1` in your
shell environment. Remove that legacy compatibility setting from shell startup
files, unset it in the current shell, and refresh uv's cached interpreter metadata:

```bash
unset SYSTEM_VERSION_COMPAT
uv sync --locked --refresh
```

For a one-command workaround without changing the shell environment:

```bash
env -u SYSTEM_VERSION_COMPAT uv sync --locked --refresh
```

# Services

| Service | Port | Description |
|---|---|---|
| Open WebUI | 3000 | Chat interface |
| Hermes | 8642 (Docker internal only) | Agent gateway, OpenAI-compatible API, tools and cron scheduler |
| llm-lab API | 8000 | Home agent FastAPI backend |
| Pipelines | 9099 | Open WebUI filter pipeline (file parsing, image OCR) |
| Postgres | 5432 | Internal only |
| llama.cpp | 8080 | Internal only, native host process |

# Startup

```bash
docker compose up -d
```

Starts Postgres, Hermes, the API (including Aerich migrations), Open WebUI, and the Pipelines service.

Start the local model server on the host before bringing up the Docker stack:

```bash
brew install llama.cpp huggingface-cli
hf auth login
hf download unsloth/Qwen3.6-35B-A3B-GGUF Qwen3.6-35B-A3B-UD-Q4_K_M.gguf --local-dir ~/models
./scripts/start_llama_server.sh
```

Docker services reach the host model server at `http://host.docker.internal:8080`.

# Shutdown

```bash
docker compose down
```

Data is preserved in Docker volumes (`postgres-data`, `hermes-home`, `open-webui`).

## Local Model Setup

This repo is configured to use llama.cpp on the macOS host, not inside Docker. That is required for Metal GPU acceleration on Apple Silicon.


Recommended model:

```bash
hf download unsloth/Qwen3.6-35B-A3B-GGUF Qwen3.6-35B-A3B-UD-Q4_K_M.gguf --local-dir ~/models
```

Start it with:

```bash
./scripts/start_llama_server.sh
```

The startup flags live in [scripts/start_llama_server.sh](/Users/kas/dev/llm-lab/scripts/start_llama_server.sh).

For unattended operation on macOS, replace the foreground process with a
launchd service (stop any manually started model server first):

```bash
uv run python scripts/install_llama_service.py
curl --fail http://localhost:8080/health
```

Model loading takes roughly 30 seconds before health returns `200`. The installer
creates `~/Library/LaunchAgents/com.llm-lab.llama-server.plist`, starts at login,
and automatically restarts the model process if it exits. Logs are written to
`~/Library/Logs/llm-lab/`. Re-run the installer after moving this checkout.
`LLAMA_MODEL`, `LLAMA_HOST` and `LLAMA_PORT` can override the installed defaults.

Then point the Docker Hermes instance at that endpoint (host-installed Hermes
has separate configuration and state):

```bash
docker compose exec hermes hermes setup model
```

Use these values:

- Base URL: `http://host.docker.internal:8080/v1`
- Model name: `Qwen3.6-35B-A3B-UD-Q4_K_M.gguf`

Restart Hermes after changing its model configuration.

## Connecting Open WebUI to Hermes

Use Hermes's native API, not the direct llama.cpp connection, when you want
agent tools, skills, memory and cron-job management. Chats run through the
Hermes harness in the existing gateway container and share its `hermes-home`
volume and cron scheduler. Tools execute inside that container, not on your
browser machine or directly on the server host.

1. Store a strong shared API key in Google Secret Manager and grant the
   configured service account `roles/secretmanager.secretAccessor` on that secret.
2. Set these non-secret values in `.env`:

   ```env
   HERMES_API_KEY_REF=gsm://your-gcp-project-id/hermes-api-key/latest
   GOOGLE_CLOUD_SM_KEYFILE=/absolute/host/path/to/service-account.json
   ```

   Compose mounts the credential file read-only into Hermes. The launcher resolves
   the key using the existing GSM client and fails explicitly if access fails.
   Port 8642 is available only on the Compose network, not published to the host.
3. Enable the endpoint and update Open WebUI's saved connections:

   ```bash
   docker compose up -d --build hermes open-webui
   uv run python scripts/fix-openwebui-config.py
   ```

   Run the repair command on the Docker host from this checkout. It verifies the
   authenticated Hermes models endpoint from inside Open WebUI, backs up the
   database, adds `http://hermes:8642/v1` without replacing existing connections,
   and restarts Open WebUI to reload its persisted settings. The key is passed
   on stdin, never printed or put in command-line arguments. Repeat after key
   rotation; restart Hermes too so it fetches the new GSM secret version.
4. Refresh Open WebUI and choose **hermes-agent** (or the name advertised by your
   Hermes profile) in the model picker. Use the default **Chat Completions** API
   type. Selecting the direct llama.cpp model bypasses the Hermes harness.

Try: "Use the cronjob tool to list my scheduled jobs. Do not change anything."
The default Hermes API-server toolset includes `cronjob`; if you customized
`platform_toolsets.api_server` in Hermes configuration, ensure it includes the
tools you need. Scheduled jobs continue running in the gateway after you close
Open WebUI. Open WebUI is not a push-notification channel for cron results;
configure a supported messaging delivery target or inspect Hermes's cron outputs.

Only trusted users should have access to this model: it can execute tools with
the gateway container's permissions and configured credentials. Open WebUI
conversations are frontend-managed; they do not automatically become the same
sessions as Slack or other gateway channels.

## Unattended cron and Slack delivery

The Docker Hermes gateway owns scheduled jobs in its persistent `hermes-home`
volume. Hermes and Open WebUI use `restart: unless-stopped`; Docker restarts them
when its engine returns, unless you explicitly stopped them.
The API, Pipelines and Postgres use the same policy so supporting services
also recover after the Docker engine restarts.

For Slack, store a JSON object containing `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN`
in GSM. Add these non-secret settings to `.env`:

```env
HERMES_SLACK_CREDENTIALS_REF=gsm://your-gcp-project-id/hermes-slack-credentials/latest
SLACK_HOME_CHANNEL=your-slack-channel-id
SLACK_ALLOWED_USERS=your-slack-member-id
```

Grant the mounted service account access to that secret, then configure the
gateway (configuration persists in the Hermes volume):

```bash
docker compose exec hermes hermes plugins enable slack-platform
docker compose exec hermes hermes config set timezone America/Los_Angeles
docker compose exec hermes hermes config set agent.api_max_retries 6
docker compose up -d --build hermes open-webui
docker compose exec hermes hermes cron list
docker compose exec hermes hermes cron status
```

The Hermes image includes Slack's SDK and ARM64-compatible Chromium/browser
tools. The API image uses the smaller `runtime` build target. Secrets are
resolved from GSM on gateway start; rotate them there and restart Hermes.
Prefer channel IDs in delivery targets to avoid channel-name lookup failures.
Conditional alert jobs should return `[SILENT]` when no alert is warranted,
rather than an empty response (which Hermes treats as a failed run).

After a host-to-Docker migration, pause the old host cron copies and disable the
host gateway's launchd service. Do not run two gateways with the same Slack
Socket Mode credentials. Keep a backup of the original cron store; preserve
job IDs, prompts, schedules, repeat counts and next-run times when moving it.
Job-specific model overrides must match the destination's provider.

This is login-started operation, not a guarantee of service before macOS login:
Docker Desktop and the model LaunchAgent require a logged-in user after reboot.
Enable Docker Desktop's **Start Docker Desktop when you sign in** option and
disable system sleep on AC power. Display sleep is fine. Closing a laptop lid,
power loss, network outages, expired credentials and third-party website
failures can still interrupt jobs; automatic restart cannot eliminate those.

# Capabilities

- **File parsing** — `.txt`, `.pdf`, `.xlsx/.xls`, `.docx/.doc`, images (PNG, JPEG, GIF, WEBP, HEIC)
  - Images: OCR via Claude Haiku vision (`ANTHROPIC_API_KEY` required)
  - `POST /files/upload` — upload a file, get parsed text + structured data back
  - `POST /files/from-gcs` — fetch and parse a file from a GCS URI (`gs://bucket/path`)
- **Open WebUI Pipelines** — filter that intercepts image attachments in chat and prepends extracted text to the model's context window
- **Search** — Google Custom Search (planned)

# Additional Settings
## Configuration and Secrets

- Non-secret runtime config belongs in `.env` (see `.env.example`).
- Use `config/master_config.yaml` as the master project config for skills, apps, and client settings.
- Secret values must stay in Google Secret Manager and be referenced with `gsm://...` URIs.
- `/clients` contains integration clients and the config/secret manager flow:
  `config -> secret manager -> client -> get_google_cloud()`.
- Required secrets are fetched via Google Secret Manager API and client creation fails if secret resolution fails.
- Runtime uses Google credentials (`GOOGLE_CLOUD_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS`).

Example:

```env
SUPPORT_EMAIL=you@example.com
GITHUB_REPO=your-org/your-repo
EXTERNAL_API_KEY_REF=gsm://llm-lab-secrets/external-api-key/latest
```

Project config files:

- `config/master_config.yaml` for project-wide service definitions
- `docs/google-secret-manager-setup.md` for Google Secret Manager setup and secret creation

## Admin settings enabled by default

This kit starts Open WebUI with:

- `ENV=dev` — enables the built-in API docs at `/docs`
- `ENABLE_API_KEYS=true` — exposes API key creation in **Account settings** (after admin enables it)

After starting Open WebUI, you can access:

- UI: `http://llm-lab:3000` (or `http://localhost:3000`)
- API docs: `http://llm-lab:3000/docs` (or `http://localhost:3000/docs`)

## Connecting the Pipelines filter to Open WebUI

After first deploy, connect the Pipelines service in the Open WebUI admin panel:

1. **Admin Panel → Settings → Connections**
2. Under OpenAI API, click **+** to add a new connection:
   - URL: `http://pipelines:9099`
   - Key: `0p3n-w3bu!`
3. Save — Open WebUI will auto-discover the **File Parser Filter**
4. **Admin Panel → Pipelines** — confirm it is listed and enabled
