# LLM Lab
https://github.com/99-antennas/llm-lab/blob/main/README.md (public)

# Requirements 
- OLLAMA enables open source models to run on CPUs (ie. your laptop)
- WEBUI a basic chat server that enables chat features with the local models.
  (docker container)

# Installation

LLM LAB – QUICK START

1. Install Ollama: https://ollama.com
2. Install Docker: https://www.docker.com/products/docker-desktop/
3. Run the setup script for your OS in the terminal:
   - macOS/Linux: scripts/setup_models.sh
   - Windows: scripts/setup_models.ps1
4. Start Open WebUI 
   - macOS/Linux: scripts/start_webui.sh
   - Windows: scripts/start_webui.ps1
5. Open browser to http://localhost:3000


# Startup
On subsequent usage just run the following line in the terminal: 
   - macOS/Linux: scripts/start_webui.sh
   - Windows: powershell -ExecutionPolicy Bypass -File ./scripts/start_webui.ps1

# Shutdown
   - macOS/Linux: scripts/stop_webui.sh
   - Windows: powershell -ExecutionPolicy Bypass -File ./scripts/stop_webui.ps1

   This stops the container but preserves all data (users, prompts, chats) stored in the `open-webui-data` Docker volume.

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
