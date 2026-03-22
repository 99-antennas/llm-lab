# Home Server

This document covers the setup and operation of an always-on macOS home server running a local AI agent stack, accessible from any device via Tailscale.

---

## Configuration Constants

Before following this guide, fill in your values here. All placeholders below reference these constants.

| Constant | Description | Your Value |
|---|---|---|
| `SERVER_HOSTNAME` | Tailscale hostname assigned to this machine | e.g. `myserver` |
| `SERVER_USER` | macOS username on the server | e.g. `kas` |
| `SERVER_LOCAL_IP` | Local WiFi IP (from `ipconfig getifaddr en0`) | e.g. `192.168.1.100` |
| `SERVER_LOCAL_HOSTNAME` | Local `.local` hostname (from `hostname`) | e.g. `MyMacBook.local` |
| `SERVER_TAILSCALE_IP` | Tailscale IP assigned to this machine | e.g. `100.x.x.x` |
| `WEBUI_ADMIN_EMAIL` | Email used for Open WebUI admin account | e.g. `you@example.com` |
| `WORK_LAPTOP_HOSTNAME` | Tailscale hostname of your work laptop | e.g. `my-work-macbook` |
| `PERSONAL_LAPTOP_HOSTNAME` | Tailscale hostname of your personal laptop | e.g. `my-personal-macbook` |

---

## Machines

| Machine | Tailscale Hostname | Role |
|---|---|---|
| This server | `SERVER_HOSTNAME` | Always-on server |
| Work laptop | `WORK_LAPTOP_HOSTNAME` | Primary machine |
| Personal laptop | `PERSONAL_LAPTOP_HOSTNAME` | Document storage |
| iPhone | — | SSH via Blink Shell, browser via Tailscale |

---

## Running Services

| Service | URL | Description |
|---|---|---|
| Open WebUI | `http://SERVER_HOSTNAME:3000` | Chat interface for Ollama — browser or phone |
| llm-lab API | `http://SERVER_HOSTNAME:8000` | Home agent API |
| API docs | `http://SERVER_HOSTNAME:8000/docs` | FastAPI Swagger UI |
| Postgres | `localhost:5432` | Internal only |
| Ollama | `localhost:11434` | Internal only, native (Metal GPU) |

All services are accessible from any enrolled Tailscale device. No ports are exposed to the public internet.

---

## Ollama Models

All models are configured with their maximum supported context window.

| Model | Context | Best for |
|---|---|---|
| `deepseek-r1:32b` | 128K | Excel, accounting, data analysis, step-by-step reasoning |
| `qwen2.5-coder:32b` | 32K | Coding tasks |
| `llama3.2` | 128K | General chat, long documents |

Models are stored in `~/.ollama/models/`.
Modelfiles with context settings are in the root of this repo (`Modelfile.*`).

To add a new model:
```bash
ollama pull <model-name>
```

To apply a custom context window for a new model:
```bash
cat > Modelfile.mymodel << 'EOF'
FROM <model-name>
PARAMETER num_ctx <max-context>
EOF
ollama create <model-name> -f Modelfile.mymodel
```

---

## Connecting from Each Device

### Laptops (work + personal)
```bash
ssh SERVER_USER@SERVER_HOSTNAME
```
SMB file access: **Finder ⌘K** → `smb://SERVER_HOSTNAME`

### iPhone
- **Terminal:** Blink Shell → host `SERVER_HOSTNAME`, user `SERVER_USER`, key `phone-SERVER_HOSTNAME`
- **Chat:** Safari → `http://SERVER_HOSTNAME:3000`
- **File transfer:** Tailscale → Send Files → lands in `~/Downloads`

---

## Starting the Stack

```bash
cd /path/to/llm-lab
docker compose up -d
```

This starts Postgres, the llm-lab API (with automatic migrations), and Open WebUI. Ollama runs natively and is always available after a reboot.

---

## Rebooting

The server is designed to recover automatically after a reboot with no manual steps.

**To reboot:**
```bash
sudo reboot
```

**After reboot, verify from another device (~2 min):**
```bash
# SSH in
ssh SERVER_USER@SERVER_HOSTNAME

# Check all containers are running
cd /path/to/llm-lab && docker compose ps

# Check API health
curl http://SERVER_HOSTNAME:8000/healthz

# Check Ollama
curl http://localhost:11434/api/tags
```

**Note:** Docker Desktop must be set to launch at login for containers to start automatically after reboot. Verify in Docker Desktop → Settings → General → "Start Docker Desktop when you log in".

---

## Troubleshooting

### SSH not connecting

```bash
# Check Tailscale is connected
tailscale status

# Check SSH service is running (run on the server)
sudo systemsetup -getremotelogin
```

If Tailscale shows the machine as offline, open the Tailscale menu bar app and reconnect, or:
```bash
tailscale up
```

---

### Docker containers not running after reboot

```bash
cd /path/to/llm-lab

# Check container status
docker compose ps

# Start if stopped
docker compose up -d

# View logs for a specific service
docker compose logs api --tail 50
docker compose logs open-webui --tail 50
docker compose logs postgres --tail 50
```

---

### API not responding

```bash
cd /path/to/llm-lab

# Check logs for errors
docker compose logs api --tail 50

# Restart just the API
docker compose restart api

# If migrations are failing
docker compose logs api | grep -i "aerich\|migration\|error"
```

---

### Open WebUI not loading

```bash
cd /path/to/llm-lab

docker compose logs open-webui --tail 50
docker compose restart open-webui
```

If you're locked out of your account, reset the password:
```bash
docker exec llm-lab-open-webui-1 python3 -c "
import sqlite3, bcrypt
new_hash = bcrypt.hashpw(b'yournewpassword', bcrypt.gensalt()).decode()
conn = sqlite3.connect('/app/backend/data/webui.db')
conn.execute(\"UPDATE auth SET password = ? WHERE email = 'WEBUI_ADMIN_EMAIL'\", (new_hash,))
conn.commit()
print('Done')
"
```

---

### Open WebUI can't reach Ollama (no models available)

Ollama runs natively, not in Docker. Check it's running:
```bash
ollama list
curl http://localhost:11434/api/tags
```

If Ollama isn't running, start it:
```bash
ollama serve &
```

---

### SMB share not mounting from another laptop

1. Verify Tailscale is connected on both machines
2. In Finder: **⌘K** → `smb://SERVER_HOSTNAME`
3. If that fails, try the IP: `smb://SERVER_TAILSCALE_IP`
4. Check File Sharing is enabled: **System Settings → General → Sharing → File Sharing**

---

### Machine sleeping with lid closed

The machine should never sleep when plugged in. If it does:

```bash
# Verify settings
pmset -g | grep -E "sleep|disablesleep"
# disablesleep should be 1, sleep should be 0

# Re-apply if needed
sudo pmset -c sleep 0
sudo pmset -c disablesleep 1
sudo pmset -c hibernatemode 0
```

Also verify: **System Settings → Lock Screen → Require password** is set to **Never**.

---

## File Access

Recommended shared folders (accessible via `smb://SERVER_HOSTNAME`):
- `~/dev`
- `~/Downloads`
- `~/Documents`
- `~/Desktop`

Files sent from iPhone via Tailscale (Taildrop) land in `~/Downloads`.

---

## Related Projects

- `llm-lab` — main application stack (API, Docker Compose, agent tools)
- `archiver` — file archival to Google Cloud Storage with local Postgres index

## Setup Documentation

- `SETUP.md` — step-by-step setup checklist with tests
- `PRD.md` — requirements and architecture decisions
