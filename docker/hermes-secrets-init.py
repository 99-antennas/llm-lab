from __future__ import annotations

import os
import pwd
from pathlib import Path

from apps.hermes_gateway import resolve_gateway_secrets


def remove_stale_api_key() -> None:
    dotenv_path = Path(os.environ.get("HERMES_HOME", "/opt/data")) / ".env"
    if not dotenv_path.is_file():
        return

    lines = dotenv_path.read_text().splitlines(keepends=True)
    filtered = []
    for line in lines:
        variable = line.partition("=")[0].strip()
        if variable.startswith("export "):
            variable = variable.removeprefix("export ").strip()
        if variable != "API_SERVER_KEY":
            filtered.append(line)
    if filtered != lines:
        dotenv_path.write_text("".join(filtered))


def main() -> None:
    remove_stale_api_key()
    env_dir = Path("/run/s6/container_environment")
    env_dir.mkdir(parents=True, exist_ok=True)
    hermes = pwd.getpwnam("hermes")
    for name, value in resolve_gateway_secrets().items():
        path = env_dir / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(value)
        os.chown(path, hermes.pw_uid, hermes.pw_gid)
        os.chmod(path, 0o400)


if __name__ == "__main__":
    main()
