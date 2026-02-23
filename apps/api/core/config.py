from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from clients.config_manager import ConfigManager

class SkillConfig(BaseModel):
    name: str
    enabled: bool = True
    description: str | None = None
    notification_email: str | None = None


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

    # Secret references must point to Google Secret Manager refs (gsm://...)
    external_api_key_ref: str | None = Field(default=None, alias="EXTERNAL_API_KEY_REF")
    google_credentials_ref: str | None = Field(default=None, alias="GOOGLE_CREDENTIALS_REF")


class ConfigBundle(BaseModel):
    settings: Settings
    skills: dict[str, SkillConfig]
    apps: dict[str, AppIntegrationConfig]


def load_skill_configs(config_dir: Path) -> dict[str, SkillConfig]:
    manager = ConfigManager(config_path=config_dir / "master_config.yaml")
    items = manager.load_service("skills")
    result: dict[str, SkillConfig] = {}
    for name, payload in items.items():
        skill = SkillConfig(name=name.replace("_", "-"), **payload)
        result[name] = skill
    return result


def load_app_configs(config_dir: Path) -> dict[str, AppIntegrationConfig]:
    manager = ConfigManager(config_path=config_dir / "master_config.yaml")
    items = manager.load_service("apps")
    result: dict[str, AppIntegrationConfig] = {}
    for name, payload in items.items():
        app = AppIntegrationConfig(name=name.replace("_", "-"), **payload)
        result[name] = app
    return result


@lru_cache(maxsize=1)
def load_config_bundle() -> ConfigBundle:
    settings = Settings()
    return ConfigBundle(
        settings=settings,
        skills=load_skill_configs(settings.config_dir),
        apps=load_app_configs(settings.config_dir),
    )
