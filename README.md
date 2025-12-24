# LLM Lab

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

## Stopping Open WebUI

macOS/Linux:

`scripts/stop_webui.sh`

Windows (PowerShell):

`scripts\stop_webui.ps1`

This stops the container but preserves all data (users, prompts, chats) stored in the `open-webui-data` Docker volume.


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
