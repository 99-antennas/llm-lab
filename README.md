# LLM Lab
https://github.com/99-antennas/llm-lab/blob/main/README.md (public)

A self-hosted AI agent stack for an always-on local machine. It pairs a host-run llama.cpp model server with a FastAPI backend, Postgres, Open WebUI, and a file parsing pipeline.

# Requirements
- [llama.cpp](https://github.com/ggml-org/llama.cpp) — runs local LLMs natively on the host (Metal GPU on Apple Silicon)
- [huggingface_hub CLI](https://huggingface.co/docs/huggingface_hub/guides/cli) — downloads GGUF model files via `hf`
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — runs Postgres, API, Open WebUI, Pipelines
- [uv](https://github.com/astral-sh/uv) — Python package manager

# Services

| Service | Port | Description |
|---|---|---|
| Open WebUI | 3000 | Chat interface |
| Hermes | internal | Agent gateway/container for orchestration and messaging |
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

Data is preserved in Docker volumes (`postgres-data`, `open-webui`).

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

Then point Hermes at that endpoint:

```bash
hermes setup model
```

Use these values:

- Base URL: `http://localhost:8080/v1`
- Model name: `Qwen3.6-35B-A3B-UD-Q4_K_M.gguf`

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
