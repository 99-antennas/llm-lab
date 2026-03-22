# PRD: Home Server Network Setup

**Version:** v1
**Status:** Active
**Machine:** Coding laptop (macOS, M-series Apple Silicon)
**Goal:** Convert this laptop into an always-on home server accessible from any device via a private, encrypted network.

---

## Configuration Constants

Fill these in before starting. Referenced throughout this document.

| Constant | Description | Your Value |
|---|---|---|
| `SERVER_HOSTNAME` | Tailscale hostname assigned to this machine | |
| `SERVER_USER` | macOS username on the server | |
| `SERVER_LOCAL_IP` | Local WiFi IP (run `ipconfig getifaddr en0`) | |
| `SERVER_LOCAL_HOSTNAME` | Local hostname (run `hostname`) | |
| `SERVER_TAILSCALE_IP` | Tailscale IP (visible after Step 5) | |

---

## 1. Objective

Configure this laptop as a persistent home server that:

- Stays on with lid closed
- Is reachable from any device (work laptop, phone) via Tailscale
- Exposes file shares over SMB for direct Finder access
- Allows remote terminal access via SSH
- Is fully compatible with the planned application stack (see Section 4)

---

## 2. Scope

This PRD covers **OS-level and network-level setup only**. Application services (llm-lab, archiver, Postgres, Ollama) are out of scope and handled in their respective projects.

---

## 3. Requirements

### 3.1 Always-On

- The laptop must not sleep when the lid is closed (requires power adapter to be connected)
- The laptop must not sleep when idle
- Display may sleep independently

### 3.2 File Sharing (SMB)

- macOS SMB file sharing must be enabled
- At minimum, the home directory or a designated `~/Shared` folder must be exposed
- Access must require a password
- Must be accessible from other devices on the Tailscale network by hostname

### 3.3 Remote Terminal Access (SSH)

- macOS Remote Login (SSH) must be enabled
- Key-based authentication must be configured for all client devices
- Password authentication may remain enabled as fallback

### 3.4 Private Network (Tailscale)

- Tailscale must be installed and authenticated on this machine
- Tailscale must be installed on: work laptop, personal laptop (when available), phone
- This machine must be reachable by its Tailscale hostname from all enrolled devices
- No ports may be publicly exposed — all access is Tailscale-only
- MagicDNS must be enabled so devices resolve by hostname (not IP)

### 3.5 Application Stack Compatibility

This network setup must support the following services running on this machine and being accessible from other enrolled Tailscale devices:

```
Work laptop / Phone
       │  (Tailscale)
       ▼
 This laptop (server)
  ├── Open WebUI        :3000  → chat interface for Ollama
  ├── llm-lab API       :8000  → programmatic access, MCP tools
  ├── Archiver API      :8001  → file indexing, GCS upload/download
  ├── Postgres          :5432  → local file metadata (internal only)
  └── SMB share                → direct file browsing in Finder
```

**Requirement:** All ports listed above must be reachable from other Tailscale devices without any additional port forwarding or firewall configuration. This must be verified as part of setup.

---

## 4. Out of Scope

- Application service installation and configuration (llm-lab, archiver, Docker, Ollama)
- GCS credentials or Google Secret Manager setup
- TLS/HTTPS (deferred — Tailscale provides transport encryption)
- Multi-user access management beyond single admin user

---

## 5. Success Criteria

- [ ] Laptop stays on with lid closed and power connected
- [ ] SSH login from work laptop succeeds using key-based auth
- [ ] SMB share mounts in Finder on work laptop via Tailscale hostname
- [ ] `ping SERVER_HOSTNAME` succeeds from work laptop
- [ ] A test HTTP server on port 3000 is reachable from work laptop over Tailscale
- [ ] A test HTTP server on port 8000 is reachable from work laptop over Tailscale
- [ ] All of the above remain functional after a full reboot of this machine

---

## 6. Security Considerations

- All remote access is via Tailscale (encrypted WireGuard tunnel)
- No ports are exposed to the public internet
- SSH key-based auth is preferred over password
- SMB share requires password authentication
- Tailscale ACLs may be configured later to restrict device-to-device access

---

## 7. Future Work

- Add Tailscale ACLs to enforce access policies between devices
- Configure launchd jobs to auto-start Docker services on boot
- Add monitoring / health check endpoints
- Document restore procedure if machine is wiped or replaced
