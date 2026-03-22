# LLM Lab
https://github.com/99-antennas/llm-lab/blob/main/README.md (public)

A self-hosted AI agent stack designed to run on an always-on local machine. Combines local LLMs via Ollama with a FastAPI backend, Postgres, Open WebUI, and a file parsing pipeline.

# Requirements
- [Ollama](https://ollama.com) — runs local LLMs natively (Metal GPU on Apple Silicon)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — runs Postgres, API, Open WebUI, Pipelines
- [uv](https://github.com/astral-sh/uv) — Python package manager

# Services

| Service | Port | Description |
|---|---|---|
| Open WebUI | 3000 | Chat interface |
| llm-lab API | 8000 | Home agent FastAPI backend |
| Pipelines | 9099 | Open WebUI filter pipeline (file parsing, image OCR) |
| Postgres | 5432 | Internal only |
| Ollama | 11434 | Internal only, native |

# Startup

```bash
docker compose up -d
```

Starts Postgres, the API (runs Aerich migrations automatically), Open WebUI, and the Pipelines service.

# Shutdown

```bash
docker compose down
```

Data is preserved in Docker volumes (`postgres-data`, `open-webui`).

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

## Friendly local URL: http://llm-lab:3000 (optional)

This kit prefers the friendly local hostname `llm-lab`. If your system does not already resolve `llm-lab`, the start script will fall back to `http://localhost:3000` and print instructions.

To enable `llm-lab`, run the helper script for your OS:

This kit prefers the friendly local hostname:

- `http://llm-lab:3000`

If your system does not already resolve `llm-lab`, the start script will fall back to `http://localhost:3000` and print instructions.

To enable `llm-lab`, add this line to your hosts file:

### macOS / Linux

Add:

`127.0.0.1   llm-lab`

Edit with:

`sudo nano /etc/hosts`

### Windows

Edit as Administrator:

`C:\Windows\System32\drivers\etc\hosts`

Add:

`127.0.0.1   llm-lab`

### macOS / Linux

```bash
scripts/setup_hostname.sh
```

### Windows (PowerShell as Administrator)

```powershell
scripts\setup_hostname.ps1
```


## WebUI base URL configuration

The start scripts set the `WEBUI_URL` environment variable to the same URL they print (either `http://llm-lab:3000` or `http://localhost:3000`). This keeps the Admin → Settings → General → WebUI URL value aligned automatically.
