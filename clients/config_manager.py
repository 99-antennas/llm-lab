from __future__ import annotations

import os
from dataclasses import field
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from clients.secret_manager import GoogleSecretManager


class ConfigManagerError(RuntimeError):
    pass


class ConfigEntry(BaseModel):
    name: str
    type: str
    value: Any | None = None
    env_var: str | None = None
    secret_ref: str | None = None
    default: Any | None = None


@dataclass
class ConfigManager:
    config_path: Path = Path("config/master_config.yaml")
    secret_manager: GoogleSecretManager = field(default_factory=GoogleSecretManager)

    def _parse(self) -> dict[str, list[ConfigEntry]]:
        if not self.config_path.exists():
            raise ConfigManagerError(f"Master config not found: {self.config_path}")

        raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ConfigManagerError("Master config must be a mapping of services to config entries")

        parsed: dict[str, list[ConfigEntry]] = {}
        for service, entries in raw.items():
            if not isinstance(entries, list):
                raise ConfigManagerError(f"Service '{service}' must define a list of entries")
            parsed[service] = [ConfigEntry.model_validate(item) for item in entries]
        return parsed

    def load(self, service_names: list[str] | None = None) -> dict[str, dict[str, Any]]:
        parsed = self._parse()
        selected = service_names or list(parsed.keys())

        state: dict[str, dict[str, Any]] = {}
        for service in selected:
            if service not in parsed:
                raise ConfigManagerError(f"Service not defined in config: {service}")
            state[service] = {}
            for entry in parsed[service]:
                state[service][entry.name] = self._resolve(service, entry)
        return state

    def load_service(self, service_name: str) -> dict[str, Any]:
        return self.load(service_names=[service_name])[service_name]

    def _resolve(self, service: str, entry: ConfigEntry) -> Any:
        if entry.type == "value":
            return entry.value

        if entry.type == "environment":
            env_key = entry.env_var or f"{service}_{entry.name}".upper()
            env_val = os.getenv(env_key)
            if env_val is not None and env_val != "":
                return env_val
            if entry.default is not None:
                return entry.default
            raise ConfigManagerError(f"Missing environment variable: {env_key}")

        if entry.type == "secret":
            if not entry.secret_ref:
                raise ConfigManagerError(
                    f"Missing secret_ref for secret entry '{service}.{entry.name}'"
                )
            try:
                return self.secret_manager.get_secret(entry.secret_ref)
            except Exception as exc:  # noqa: BLE001
                raise ConfigManagerError(
                    f"Unable to resolve secret for '{service}.{entry.name}' "
                    f"from '{entry.secret_ref}': {exc}"
                ) from exc

        raise ConfigManagerError(f"Unsupported entry type: {entry.type}")
