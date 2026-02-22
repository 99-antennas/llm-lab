from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SkillConfig(BaseModel):
    name: str
    enabled: bool = True
    description: str | None = None


class AppIntegrationConfig(BaseModel):
    name: str
    enabled: bool = True
    owner_email: str | None = None
    github_repo: str | None = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env",),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = Field(default="dev", alias="APP_ENV")
    app_name: str = Field(default="home-agent", alias="APP_NAME")
    config_dir: Path = Field(default=Path("config"), alias="CONFIG_DIR")

    # Non-secret configuration values can live in .env
    support_email: str | None = Field(default=None, alias="SUPPORT_EMAIL")
    github_repo: str | None = Field(default=None, alias="GITHUB_REPO")

    # Secret references must point to 1Password (op://...)
    external_api_key_ref: str | None = Field(default=None, alias="EXTERNAL_API_KEY_REF")
    google_credentials_ref: str | None = Field(default=None, alias="GOOGLE_CREDENTIALS_REF")


class ConfigBundle(BaseModel):
    settings: Settings
    skills: dict[str, SkillConfig]
    apps: dict[str, AppIntegrationConfig]


def _load_yaml_objects(path: Path) -> list[dict]:
    if not path.exists():
        return []
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    if content is None:
        return []
    if not isinstance(content, list):
        raise ValueError(f"Expected list in {path}")
    return content


def load_skill_configs(config_dir: Path) -> dict[str, SkillConfig]:
    items = _load_yaml_objects(config_dir / "skills.yaml")
    result: dict[str, SkillConfig] = {}
    for item in items:
        skill = SkillConfig.model_validate(item)
        result[skill.name] = skill
    return result


def load_app_configs(config_dir: Path) -> dict[str, AppIntegrationConfig]:
    items = _load_yaml_objects(config_dir / "apps.yaml")
    result: dict[str, AppIntegrationConfig] = {}
    for item in items:
        app = AppIntegrationConfig.model_validate(item)
        result[app.name] = app
    return result


@lru_cache(maxsize=1)
def load_config_bundle() -> ConfigBundle:
    settings = Settings()
    return ConfigBundle(
        settings=settings,
        skills=load_skill_configs(settings.config_dir),
        apps=load_app_configs(settings.config_dir),
    )
