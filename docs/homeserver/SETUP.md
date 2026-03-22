# Home Server Setup Log

Fill in the constants below before starting, then track each step as you complete it.

---

## Your Constants

```
SERVER_HOSTNAME=         # Tailscale hostname (e.g. myserver) — assigned in Step 5
SERVER_USER=             # macOS username (e.g. kas)
SERVER_LOCAL_IP=         # Local WiFi IP — run: ipconfig getifaddr en0
SERVER_LOCAL_HOSTNAME=   # Local hostname — run: hostname
SERVER_TAILSCALE_IP=     # Tailscale IP — visible after Step 5
```

---

## Step 1 — Prevent Sleep on Lid Close

**What:** Keep the laptop awake when the lid is closed (clamshell mode), as long as it's plugged in.

**Instructions:**

**System Settings:**
1. **System Settings → Battery** → Enable **"Prevent automatic sleeping on power adapter when the display is off"**
2. **System Settings → Lock Screen** → Set **"Require password after screen saver begins or display is turned off"** to **Never** — without this, closing the lid locks the screen and blocks SSH connections until unlocked locally

**Terminal (run once):**
```bash
sudo pmset -c sleep 0          # disable idle sleep on power adapter
sudo pmset -c hibernatemode 0  # disable hibernate on power adapter
sudo pmset -c disksleep 0      # disable disk sleep on power adapter
sudo pmset -c disablesleep 1   # force disable sleep on lid close (Apple Silicon)
```

> **Note:** The `-c` flag applies these settings only when plugged into power, so battery behavior is unaffected. `disablesleep 1` is required on Apple Silicon — without it the lid-close triggers sleep regardless of other settings.

**Status:** [ ] Complete

**Test:**
1. Plug in power adapter
2. Close the lid
3. Wait 5 minutes
4. SSH into the machine from another laptop: `ssh SERVER_USER@SERVER_LOCAL_IP`
5. Run `uptime` — confirm the machine has been running continuously
6. [ ] Test passed

---

## Step 2 — Enable SSH (Remote Login)

**What:** Allow terminal access from other devices.

**Instructions:**

1. Open **System Settings → General → Sharing**
2. Enable **Remote Login**
3. Set "Allow access for" to your user account (or all users)
4. Note the SSH command shown — yours will be: `ssh SERVER_USER@SERVER_LOCAL_HOSTNAME`

**Status:** [ ] Complete

**Test (from this machine first):**
```bash
ssh localhost
# Should connect — type exit when done
```

**Test (from another laptop, on same WiFi):**
```bash
ssh SERVER_USER@SERVER_LOCAL_HOSTNAME
# Should connect without issues
```

- [ ] SSH works on same network

---

## Step 3 — Set Up SSH Key Authentication

**What:** Allow passwordless SSH from your other devices using key pairs.

**Instructions (run on each client laptop):**

```bash
# Generate a key if you don't have one
ssh-keygen -t ed25519 -C "work-laptop"

# Copy the public key to the server
ssh-copy-id SERVER_USER@SERVER_LOCAL_HOSTNAME
# Enter your password when prompted — this is the last time you'll need it
```

**Verify it worked:**
```bash
ssh SERVER_USER@SERVER_LOCAL_HOSTNAME
# Should log in without asking for a password
```

**Status:** [ ] Complete

**Test:**
- [ ] SSH login from work laptop succeeds without a password prompt
- [ ] SSH login from personal laptop succeeds without a password prompt

---

## Step 4 — Enable SMB File Sharing

**What:** Expose folders on this machine as network drives mountable from Finder.

**Instructions:**

1. Open **System Settings → General → Sharing**
2. Enable **File Sharing**
3. Click the **Options** button → check **Share files and folders using SMB** → check your username
4. Under **Shared Folders**, add the folders you want to share (e.g. `~/Documents`, `~/Downloads`, `~/Desktop`, `~/dev`)
5. Set permissions as desired (Read & Write for your user)

**Status:** [ ] Complete

**Test (from another laptop, on same WiFi):**
1. In Finder: **Go → Connect to Server** (⌘K)
2. Enter: `smb://SERVER_LOCAL_IP`
3. Authenticate with your username and password
4. The share should mount and appear in Finder sidebar

- [ ] SMB share mounts in Finder on same network

---

## Step 5 — Install Tailscale on This Machine

**What:** Join this machine to your private Tailscale network.

**Instructions:**

1. Download Tailscale from: https://tailscale.com/download/mac
2. Install and open the app
3. Click **Log in** and authenticate with your **personal** account (not a work-managed account)
4. After login, this machine will appear in your Tailscale admin console
5. Note the Tailscale hostname assigned — this is your `SERVER_HOSTNAME`
6. Enable **MagicDNS** in the Tailscale admin console:
   - Go to: https://login.tailscale.com/admin/dns
   - Enable MagicDNS

> **Note:** If Tailscale is already installed with a work account, log out first: `tailscale logout && tailscale up`

**Fill in your constants now:**
```
SERVER_HOSTNAME=          # the hostname Tailscale assigned this machine
SERVER_TAILSCALE_IP=      # the IP shown in tailscale status
```

**Status:** [ ] Complete

**Test:**
```bash
tailscale status
# Should show this machine as connected and list other enrolled devices
```

- [ ] Machine shows as connected in `tailscale status`
- [ ] Machine visible in Tailscale admin console

---

## Step 6 — Install Tailscale on All Client Devices

**What:** Enroll your other laptops and phone in the same Tailscale network.

**Instructions:**

1. Download and install Tailscale on each device
2. Log in with the **same personal Tailscale account** on each
3. All machines should appear in the Tailscale admin console

**For iPhone:** Install Tailscale from the App Store.

**Status:** [ ] Complete

**Test (from each client device):**
```bash
ping SERVER_HOSTNAME
# Should receive replies — hostname resolves via MagicDNS
```

```bash
ssh SERVER_USER@SERVER_HOSTNAME
# Should connect using your SSH key — over Tailscale, not local network
```

- [ ] `ping SERVER_HOSTNAME` succeeds from work laptop
- [ ] `ssh SERVER_USER@SERVER_HOSTNAME` works from work laptop
- [ ] `ssh SERVER_USER@SERVER_HOSTNAME` works from personal laptop

---

## Step 7 — Mount SMB Share over Tailscale

**What:** Verify the file share is accessible remotely (not just on local WiFi).

**Instructions:**

1. On your work laptop, disconnect from the home WiFi (or use your phone as hotspot to simulate being away from home)
2. Verify Tailscale is still connected

**Test:**
1. In Finder: **Go → Connect to Server** (⌘K)
2. Enter: `smb://SERVER_HOSTNAME`
3. Authenticate and mount the share

- [ ] SMB share mounts via Tailscale hostname
- [ ] File access works when not on home WiFi

---

## Step 8 — Verify Application Port Accessibility over Tailscale

**What:** Confirm that application services (llm-lab, Open WebUI, etc.) will be reachable from other devices once running.

**Instructions — run on this machine:**

```bash
python3 -m http.server 3000 &
python3 -m http.server 8000 &
```

**Test (from another laptop, over Tailscale):**
```bash
curl http://SERVER_HOSTNAME:3000
# Should return an HTML directory listing

curl http://SERVER_HOSTNAME:8000
# Should return an HTML directory listing
```

**Cleanup (on this machine after testing):**
```bash
kill $(lsof -ti:3000) $(lsof -ti:8000)
```

- [ ] Port 3000 reachable from work laptop over Tailscale
- [ ] Port 8000 reachable from work laptop over Tailscale

---

## Step 9 — Reboot Verification

**What:** Confirm everything survives a full reboot.

**Instructions:**

1. Reboot this machine: `sudo reboot`
2. Wait ~2 minutes for it to fully start
3. Keep the lid closed (on power)

**Test (from another laptop):**
```bash
ssh SERVER_USER@SERVER_HOSTNAME
uptime
```

1. In Finder: mount the SMB share again via Tailscale hostname
2. Confirm it connects successfully

- [ ] SSH works after reboot (lid closed)
- [ ] SMB share mounts after reboot
- [ ] Tailscale reconnects automatically after reboot

---

## Step 10 — Set Up SSH from iPhone (Optional)

**What:** Access the server terminal from your phone using Blink Shell.

**Instructions:**

1. Install **Blink Shell** from the App Store
2. Open Blink → type `config` → **Keys** → **+**
   - Type: `ED25519`, Name: `phone-SERVER_HOSTNAME`
   - Tap **Save** → tap the key → **Copy Public Key**
3. On the server, add the public key:
```bash
echo "PASTE_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
```
4. In Blink → `config` → **Hosts** → **+**
   - Host: `SERVER_HOSTNAME`, Hostname: `SERVER_HOSTNAME`, User: `SERVER_USER`, Key: `phone-SERVER_HOSTNAME`

**Status:** [ ] Complete

**Test:**
```bash
# In Blink terminal
ssh SERVER_HOSTNAME
```

- [ ] SSH from iPhone connects successfully
- [ ] `http://SERVER_HOSTNAME:3000` loads Open WebUI in Safari

---

## Step 11 — Friendly SSH Aliases (Optional)

**What:** Set up short aliases so you can type `ssh homeserver` instead of the full command.

**Instructions (run on each client laptop):**

Add to `~/.ssh/config`:

```
Host homeserver
    HostName SERVER_LOCAL_IP
    User SERVER_USER

Host homeserver-ts
    HostName SERVER_HOSTNAME
    User SERVER_USER
```

- `homeserver` — works on home WiFi
- `homeserver-ts` — works anywhere via Tailscale

**Status:** [ ] Complete

---

## Summary

| Step | Description                            | Status |
|------|----------------------------------------|--------|
| 1    | Prevent sleep on lid close             | [ ]    |
| 2    | Enable SSH                             | [ ]    |
| 3    | SSH key auth from all laptops          | [ ]    |
| 4    | Enable SMB file sharing                | [ ]    |
| 5    | Install Tailscale on server            | [ ]    |
| 6    | Install Tailscale on all client devices| [ ]    |
| 7    | SMB over Tailscale                     | [ ]    |
| 8    | Port accessibility over Tailscale      | [ ]    |
| 9    | Reboot verification                    | [ ]    |
| 10   | SSH from iPhone (optional)             | [ ]    |
| 11   | Friendly SSH aliases (optional)        | [ ]    |

**Setup complete when Steps 1–9 are checked.**

Once complete, this machine is ready to run llm-lab, archiver, and any other Docker-based services — all accessible from your devices over Tailscale.
