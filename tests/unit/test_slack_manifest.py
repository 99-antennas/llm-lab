import json
from pathlib import Path

import pytest

import hermes_plugins.slack_workspace as plugin
from hermes_plugins.slack_workspace import manifest as m

SHACK_MANIFEST = json.loads((Path(__file__).parents[2] / "slack-manifest.json").read_text())
SHACK_SCOPES = set(SHACK_MANIFEST["oauth_config"]["scopes"]["bot"])


def test_external_scopes_never_exceed_shacks():
    assert set(m.EXTERNAL_BOT_SCOPES) <= SHACK_SCOPES


def test_external_events_never_exceed_shacks():
    assert set(m.EXTERNAL_BOT_EVENTS) <= set(SHACK_MANIFEST["settings"]["event_subscriptions"]["bot_events"])


def test_no_forbidden_or_admin_scopes_granted():
    granted = set(m.build_manifest("Prometheus")["oauth_config"]["scopes"]["bot"])
    assert not granted & set(m.FORBIDDEN_SCOPES)
    assert not [s for s in granted if s.startswith("admin")]


@pytest.mark.parametrize("scope", [
    "channels:manage", "channels:join", "channels:write.invites", "groups:write",
    "groups:write.invites", "mpim:write", "chat:write.public", "chat:write.customize",
    "users:read.email", "admin.conversations:write",
])
def test_risky_scopes_are_forbidden(scope):
    assert m._is_forbidden(scope)


def test_editing_scope_list_to_add_forbidden_scope_is_refused(monkeypatch):
    monkeypatch.setattr(m, "EXTERNAL_BOT_SCOPES", m.EXTERNAL_BOT_SCOPES + ("channels:write.invites",))
    with pytest.raises(m.ManifestError, match="channels:write.invites"):
        m.build_manifest("Prometheus")


def test_communication_scopes_present():
    granted = set(m.build_manifest("Prometheus")["oauth_config"]["scopes"]["bot"])
    assert {"chat:write", "channels:history", "groups:history", "im:history", "im:write",
            "users:read", "app_mentions:read", "channels:read", "groups:read"} <= granted


def test_manifest_shape():
    out = m.build_manifest("Ray McLendon Prometheus", "Ray's agent")
    assert "user" not in out["oauth_config"]["scopes"]
    assert "slash_commands" not in out["features"]
    assert out["features"]["bot_user"]["display_name"] == "ray-mclendon-prometheus"
    assert out["display_information"]["description"] == "Ray's agent"
    assert out["settings"]["socket_mode_enabled"] is True
    assert out["settings"]["org_deploy_enabled"] is False


@pytest.mark.parametrize(("kwargs", "match"), [
    ({"app_name": ""}, "required"),
    ({"app_name": "x" * 36}, "35"),
    ({"app_name": "Bot", "description": "d" * 141}, "140"),
    ({"app_name": "Bot", "display_name": "Has Spaces"}, "display_name"),
    ({"app_name": "Bot", "background_color": "red"}, "background_color"),
])
def test_invalid_inputs(kwargs, match):
    with pytest.raises(m.ManifestError, match=match):
        m.build_manifest(**kwargs)


def test_package_has_json_and_steps():
    pkg = m.manifest_package("Prometheus")
    assert json.loads(pkg["manifest_json"]) == pkg["manifest"]
    assert any("/invite @prometheus" in step for step in pkg["setup_steps"])
    assert any(line.startswith("channels:write.invites:") for line in pkg["not_granted"])


def test_tool_returns_package_and_errors():
    out = json.loads(plugin.slack_bot_manifest({"app_name": "Prometheus"}))
    assert out["manifest"]["display_information"]["name"] == "Prometheus"
    err = json.loads(plugin.slack_bot_manifest({}))
    assert err["error"] == "invalid_manifest_input"


def test_can_do_covers_every_granted_scope():
    covered = {scope for _line, scopes in m.CAN_DO for scope in scopes}
    assert covered == set(m.EXTERNAL_BOT_SCOPES)


def test_permissions_summary_lists_can_and_cannot():
    summary = m.manifest_package("Prometheus")["permissions_summary"]
    assert summary.startswith("*What Prometheus can do*")
    assert "*What it can't do*" in summary
    for line, _scopes in m.CAN_DO:
        assert f"• {line}" in summary
    for line in m.CANNOT_DO:
        assert f"• {line}" in summary
    assert "Add or remove people" in summary
