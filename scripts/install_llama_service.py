"""Install a login-started, launchd-supervised llama.cpp server on macOS."""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

LABEL = "com.llm-lab.llama-server"


def service_config(root: Path, home: Path, binary: Path) -> dict:
    logs = home / "Library" / "Logs" / "llm-lab"
    return {
        "Label": LABEL,
        "ProgramArguments": ["/bin/bash", str(root / "scripts/start_llama_server.sh")],
        "WorkingDirectory": str(root),
        "EnvironmentVariables": {
            "HOME": str(home),
            "PATH": f"{binary.parent}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
            "LLAMA_MODEL": os.environ.get(
                "LLAMA_MODEL", str(home / "models/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf")
            ),
            "LLAMA_HOST": os.environ.get("LLAMA_HOST", "0.0.0.0"),
            "LLAMA_PORT": os.environ.get("LLAMA_PORT", "8080"),
        },
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "StandardOutPath": str(logs / "llama-server.log"),
        "StandardErrorPath": str(logs / "llama-server.error.log"),
    }


def main() -> None:
    if sys.platform != "darwin":
        raise RuntimeError("This installer requires macOS launchd")
    binary = shutil.which("llama-server")
    if not binary:
        raise RuntimeError("Install llama.cpp before installing its service")
    root = Path(__file__).resolve().parents[1]
    home = Path.home()
    config = service_config(root, home, Path(binary))
    if not Path(config["EnvironmentVariables"]["LLAMA_MODEL"]).is_file():
        raise FileNotFoundError("Download the configured GGUF model before installing")
    path = home / "Library/LaunchAgents" / f"{LABEL}.plist"
    path.parent.mkdir(parents=True, exist_ok=True)
    (home / "Library/Logs/llm-lab").mkdir(parents=True, exist_ok=True)
    domain = f"gui/{os.getuid()}"
    # Query the domain's loaded services before replacing this one.
    result = subprocess.run(
        ["launchctl", "list"], check=True, capture_output=True, text=True
    )
    if any(line.split()[-1:] == [LABEL] for line in result.stdout.splitlines()):
        subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], check=True)
    path.write_bytes(plistlib.dumps(config))
    subprocess.run(["plutil", "-lint", str(path)], check=True)
    subprocess.run(["launchctl", "bootstrap", domain, str(path)], check=True)
    print(f"Installed {LABEL}; starts at login and restarts if it exits.")
    print(f"Logs: {home / 'Library/Logs/llm-lab'}")


if __name__ == "__main__":
    main()
