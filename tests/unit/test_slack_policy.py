import pytest

import hermes_plugins.slack_workspace as plugin
from hermes_plugins.slack_workspace import policy

OWNER, RAY, PROMETHEUS = "U0GEPK3FW", "U0577L3CTT9", "U0CF5SYBJ5N"


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    for k in ("SLACK_TOOL_LIMITS", "SLACK_SAFE_TOOLS", "SLACK_FILE_ROOTS"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SLACK_FULL_ACCESS_USERS", OWNER)
    monkeypatch.setenv("SLACK_FILE_ROOTS", str(tmp_path / "workspace"))
    (tmp_path / "workspace" / "retreat-planning").mkdir(parents=True)
    return tmp_path


@pytest.mark.parametrize(("user", "chat", "chat_type", "limited"), [
    (OWNER, "C0CF5QW6YM6", "group", True),      # owner in a channel: same limits as everyone
    (OWNER, "D0OWNERDM", "dm", False),           # owner's DM: full access
    (OWNER, "C0GROUPDM", "dm", True),            # owner in a group DM (Hermes says "dm"): limited
    (OWNER, "G0LEGACYMPIM", "dm", True),         # legacy group DM IDs too
    (RAY, "D0RAYDM", "dm", True),                # anyone else's DM: limited
    (RAY, "C0CF5QW6YM6", "group", True),
    (PROMETHEUS, "C0CF5QW6YM6", "group", True),  # bots: limited
    (PROMETHEUS, "D0BOTDM", "dm", True),
    ("", "D0X", "dm", True),                     # unknown sender: limited
])
def test_who_is_limited(user, chat, chat_type, limited):
    assert policy.is_limited("slack", user, chat, chat_type) is limited


def test_other_platforms_and_cron_unaffected():
    assert not policy.is_limited("cron", RAY, "", "")
    assert not policy.is_limited("", RAY, "", "")
    assert not policy.is_limited("telegram", RAY, "C1", "group")


def test_limits_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("SLACK_TOOL_LIMITS", "off")
    assert not policy.is_limited("slack", RAY, "C1", "group")


@pytest.mark.parametrize("tool", ["terminal", "execute_code", "browser_navigate", "browser_vault_fill",
                                  "computer_use", "cronjob_manage", "delegate_task", "manage_connections",
                                  "process_manage", "skill_manage", "memory", "session_search",
                                  "image_generate", "text_to_speech", "some_future_mcp_tool"])
def test_blocked_tools(tool):
    assert "isn't available on Slack" in policy.block_reason(tool, {})


@pytest.mark.parametrize("tool", ["slack_channel_members", "slack_post_message", "slack_get_replies",
                                  "web_search", "web_extract", "vision_analyze", "skills_list",
                                  "skill_view", "todo_list", "clarify", "slack_bot_manifest"])
def test_safe_tools(tool):
    assert policy.block_reason(tool, {}) is None


def test_file_tools_only_inside_workspace(env):
    plan = str(env / "workspace" / "retreat-planning" / "PLAN.md")
    for tool in ("read_file", "write_file", "patch", "search_files"):
        assert policy.block_reason(tool, {"path": plan}) is None
    for bad in ("/opt/data/.env", "/opt/data/auth.json", "PLAN.md", "~/x",
                str(env / "workspace" / ".." / "secrets"), str(env / "workspace-evil" / "x"), ""):
        assert "files are limited" in policy.block_reason("read_file", {"path": bad})
    assert "files are limited" in policy.block_reason("search_files", {"pattern": "token"})


def test_file_symlink_escape_blocked(env):
    link = env / "workspace" / "escape"
    link.symlink_to("/etc")
    assert policy.block_reason("read_file", {"path": str(link / "passwd")})


def test_safe_tools_override(monkeypatch):
    monkeypatch.setenv("SLACK_SAFE_TOOLS", "web_search, terminal")
    assert policy.block_reason("terminal", {}) is None
    assert policy.block_reason("slack_post_message", {})


def test_cool_tools_text():
    text = policy.cool_tools_text()
    assert text.startswith("*What Shack can do for you on Slack*")
    assert "Search the web and read web pages" in text
    assert "Run terminal commands or code" in text
    assert "Bots and agents" in text


def test_tools_hint_lists_allowed():
    hint = policy.tools_hint()
    assert "slack_post_message" in hint and "terminal" not in hint


# -- hooks ---------------------------------------------------------------------------------------


def session(monkeypatch, **values):
    env = {"HERMES_SESSION_PLATFORM": "slack", **values}
    monkeypatch.setattr(plugin, "_session_value", lambda name: env.get(name, ""))


def test_pre_tool_call_blocks_bot_terminal(monkeypatch):
    session(monkeypatch, HERMES_SESSION_USER_ID=PROMETHEUS, HERMES_SESSION_CHAT_ID="C0CF5QW6YM6",
            HERMES_SESSION_CHAT_TYPE="group")
    out = plugin._pre_tool_call(tool_name="terminal", args={"command": "cat /opt/data/.env"})
    assert out["action"] == "block" and "isn't available on Slack" in out["message"]
    assert plugin._pre_tool_call(tool_name="slack_channel_members", args={}) is None


def test_pre_tool_call_owner_dm_unrestricted(monkeypatch):
    session(monkeypatch, HERMES_SESSION_USER_ID=OWNER, HERMES_SESSION_CHAT_ID="D0OWNERDM",
            HERMES_SESSION_CHAT_TYPE="dm")
    assert plugin._pre_tool_call(tool_name="terminal", args={"command": "ls"}) is None


def test_pre_tool_call_outside_slack(monkeypatch):
    monkeypatch.setattr(plugin, "_session_value", lambda name: "")
    assert plugin._pre_tool_call(tool_name="terminal", args={}) is None


def test_pre_llm_call_adds_hint_in_limited_dm(monkeypatch):
    session(monkeypatch, HERMES_SESSION_USER_ID=RAY, HERMES_SESSION_CHAT_ID="D0RAYDM",
            HERMES_SESSION_CHAT_TYPE="dm")
    out = plugin._pre_llm_call(platform="slack")
    assert out["context"].startswith("[On Slack you can only use these tools:")


def test_pre_llm_call_no_hint_for_owner_dm(monkeypatch):
    session(monkeypatch, HERMES_SESSION_USER_ID=OWNER, HERMES_SESSION_CHAT_ID="D0OWNERDM",
            HERMES_SESSION_CHAT_TYPE="dm")
    assert plugin._pre_llm_call(platform="slack") is None


@pytest.mark.parametrize("text", ["help", "Help!", "cool-tools", "cool_tools", "Cool tools?", "tools",
                                  "@Shack help", "@shack, cool-tools",
                                  "What can you do?", "  help.  "])
def test_tools_requests(text):
    assert policy.is_tools_request(text)


@pytest.mark.parametrize("text", ["help me book the cabin", "can you help Ray?", "", "/help",
                                  "tools for the retreat", "<@U0577L3CTT9> help", "@Ray help"])
def test_not_tools_requests(text):
    assert not policy.is_tools_request(text)


def test_dispatch_hook_rewrites_help_to_command(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    monkeypatch.delenv("SLACK_IGNORE_OTHER_USER_MENTIONS", raising=False)
    ev = SimpleNamespace(source=SimpleNamespace(platform=SimpleNamespace(value="slack")),
                         raw_message={"channel": "C0CF5QW6YM6", "ts": "1.0", "user": "U0577L3CTT9"},
                         text="help")
    assert asyncio.run(plugin._pre_gateway_dispatch(event=ev)) == {"action": "rewrite", "text": "/cool-tools"}
    ev.text = "help me with dates"
    assert asyncio.run(plugin._pre_gateway_dispatch(event=ev)) is None
