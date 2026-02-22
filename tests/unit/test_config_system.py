from pathlib import Path

from apps.api.core.config import (
    AppIntegrationConfig,
    Settings,
    SkillConfig,
    load_app_configs,
    load_skill_configs,
)


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_NAME", "home-agent-test")
    monkeypatch.setenv("SUPPORT_EMAIL", "ops@example.com")
    monkeypatch.setenv("GITHUB_REPO", "99-antennas/llm-lab")

    settings = Settings()

    assert settings.app_env == "test"
    assert settings.app_name == "home-agent-test"
    assert settings.support_email == "ops@example.com"
    assert settings.github_repo == "99-antennas/llm-lab"


def test_yaml_skill_and_app_configs_parse(tmp_path: Path):
    (tmp_path / "skills.yaml").write_text(
        "- name: approval-notifier\n  enabled: true\n",
        encoding="utf-8",
    )
    (tmp_path / "apps.yaml").write_text(
        "- name: github-poller\n  enabled: true\n",
        encoding="utf-8",
    )

    skills = load_skill_configs(tmp_path)
    apps = load_app_configs(tmp_path)

    assert skills["approval-notifier"] == SkillConfig(name="approval-notifier", enabled=True)
    assert apps["github-poller"] == AppIntegrationConfig(name="github-poller", enabled=True)
