from pathlib import Path

from apps.api.core.config import (
    AppIntegrationConfig,
    Settings,
    SkillConfig,
    load_app_configs,
    load_skill_configs,
)
from clients.config_manager import ConfigManager, ConfigManagerError


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_NAME", "home-agent-test")
    monkeypatch.setenv("SUPPORT_EMAIL", "ops@example.com")

    settings = Settings()

    assert settings.app_env == "test"
    assert settings.app_name == "home-agent-test"
    assert settings.support_email == "ops@example.com"


def test_master_config_skill_and_app_configs_parse(tmp_path: Path):
    (tmp_path / "master_config.yaml").write_text(
        """
skills:
  - name: notification
    type: value
    value:
      enabled: true
      notification_email: kas@99antennas.com
apps:
  - name: github_poller
    type: value
    value:
      enabled: true
      github_repo: 99-antennas/llm-lab
""",
        encoding="utf-8",
    )

    skills = load_skill_configs(tmp_path)
    apps = load_app_configs(tmp_path)

    assert skills["notification"] == SkillConfig(
        name="notification",
        enabled=True,
        notification_email="kas@99antennas.com",
    )
    assert apps["github_poller"] == AppIntegrationConfig(
        name="github-poller", enabled=True, github_repo="99-antennas/llm-lab"
    )


def test_config_manager_raises_for_missing_environment_var(tmp_path: Path):
    (tmp_path / "master_config.yaml").write_text(
        """
service:
  - name: api_key
    type: environment
    env_var: MISSING_API_KEY
""",
        encoding="utf-8",
    )

    manager = ConfigManager(config_path=tmp_path / "master_config.yaml")
    try:
        manager.load_service("service")
        assert False, "expected ConfigManagerError"
    except ConfigManagerError:
        assert True
