from datetime import timezone

import hermes_plugins.slack_workspace as plugin
from hermes_plugins.slack_workspace.activity import ActivityCache, collect, format_digest
from hermes_plugins.slack_workspace.workspace import SlackWorkspace

SHACK, KAS, RAY = "U0SHACK", "U0KAS", "U0RAY"
NAMES = {SHACK: "Shack", KAS: "kas", RAY: "Ray McLendon"}
NOW = 1_800_000_000.0


def msg(user, text, ago_min, **extra):
    return {"user": user, "text": text, "ts": f"{NOW - ago_min * 60:.6f}", **extra}


ROOT = msg(SHACK, "Here's a Slack app manifest for ray-mclendon-prometheus", 10, reply_count=2,
           latest_reply=f"{NOW - 5 * 60:.6f}")
ROOT["thread_ts"] = ROOT["ts"]
TAGGED = msg(KAS, "<@U0RAY> see if you can enable this manifest", 7, thread_ts=ROOT["ts"])
FOLLOW = msg(KAS, "I may need to enable adding prometheus", 5, thread_ts=ROOT["ts"])
TOP = msg(RAY, "what's for dinner <!here>? see <https://x.com|menu> in <#C0CF5QW6YM6|retreat-planning>", 3)


class FakeSlack:
    def __init__(self):
        self.calls = []

    def __call__(self, method, **p):
        self.calls.append((method, p))
        if method == "conversations.history":
            return {"messages": [TOP, ROOT, msg(RAY, "", 2, subtype="channel_join")]}
        if method == "conversations.replies":
            return {"messages": [ROOT, TAGGED, FOLLOW]}
        if method == "auth.test":
            return {"user_id": SHACK}
        if method == "users.list":
            return {"members": [{"id": u, "name": n.lower(), "profile": {"display_name": n}} for u, n in NAMES.items()]}
        if method == "conversations.info":
            return {"channel": {"id": p["channel"], "name": "retreat-planning", "is_private": True}}
        raise AssertionError(method)


def test_collect_merges_top_level_and_thread_replies_in_order():
    fake = FakeSlack()
    out = collect(fake, "C0CF5QW6YM6", NOW - 86400)
    assert [m["text"][:12] for m in out] == [ROOT["text"][:12], TAGGED["text"][:12], FOLLOW["text"][:12],
                                            TOP["text"][:12]]


def test_digest_formats_names_threads_and_markup():
    out = collect(FakeSlack(), "C0CF5QW6YM6", NOW - 86400)
    digest = format_digest(out, "retreat-planning", SHACK, NAMES.get, timezone.utc, 24)
    lines = digest.splitlines()
    assert lines[0].startswith("[Recent activity in #retreat-planning across the channel and all its threads")
    assert lines[1].endswith("Shack (you): Here's a Slack app manifest for ray-mclendon-prometheus")
    assert "kas [in thread: Here's a Slack app manifest for ray-mcl…]: @Ray McLendon see if" in lines[2]
    assert "Ray McLendon: what's for dinner @here? see menu (https://x.com) in #retreat-planning" in lines[4]


def test_digest_marks_current_thread_and_excludes_current_message():
    out = collect(FakeSlack(), "C0CF5QW6YM6", NOW - 86400)
    digest = format_digest(out, "retreat-planning", SHACK, NAMES.get, timezone.utc, 24,
                           current_thread=ROOT["ts"], exclude_ts=FOLLOW["ts"])
    assert "[this thread's first message]" in digest
    assert "kas [this thread]: @Ray McLendon" in digest
    assert "I may need" not in digest


def test_digest_trims_oldest_to_budget():
    many = [msg(KAS, f"message number {i} " + "x" * 100, 100 - i) for i in range(100)]
    digest = format_digest(many, "c", SHACK, NAMES.get, timezone.utc, 24, max_messages=60, max_chars=2000)
    assert len(digest) <= 2000
    assert "message number 99" in digest and "message number 39 " not in digest


def test_empty_digest():
    assert format_digest([], "c", SHACK, NAMES.get, timezone.utc, 24) == ""


def test_cache_reuses_within_ttl():
    now = [0.0]
    fake = FakeSlack()
    cache = ActivityCache(ttl_seconds=60, clock=lambda: now[0])
    cache.get(fake, "C1", 24, NOW)
    cache.get(fake, "C1", 24, NOW)
    assert sum(1 for m, _ in fake.calls if m == "conversations.history") == 1
    now[0] = 61
    cache.get(fake, "C1", 24, NOW)
    assert sum(1 for m, _ in fake.calls if m == "conversations.history") == 2


def test_hook_injects_digest_for_slack_channels(monkeypatch):
    fake = FakeSlack()
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setattr(plugin, "_workspace", ("xoxb-test", SlackWorkspace(fake)))
    monkeypatch.setattr(plugin, "_activity_cache", ActivityCache())
    monkeypatch.setattr(plugin.time, "time", lambda: NOW)
    env = {"HERMES_SESSION_CHAT_ID": "C0CF5QW6YM6", "HERMES_SESSION_THREAD_ID": ROOT["ts"],
           "HERMES_SESSION_MESSAGE_ID": FOLLOW["ts"]}
    monkeypatch.setattr(plugin, "_session_value", lambda name: env.get(name, ""))
    out = plugin._pre_llm_call(platform="slack")
    assert "kas [this thread]: @Ray McLendon see if you can enable this manifest" in out["context"]
    assert plugin._pre_llm_call(platform="telegram") is None
    env["HERMES_SESSION_CHAT_ID"] = "D0DM"
    assert plugin._pre_llm_call(platform="slack") is None


def test_hook_disabled_and_fails_open(monkeypatch):
    monkeypatch.setattr(plugin, "_session_value", lambda name: "C0CF5QW6YM6" if name.endswith("CHAT_ID") else "")
    monkeypatch.setenv("SLACK_ACTIVITY_HOURS", "0")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    assert plugin._pre_llm_call(platform="slack") is None
    monkeypatch.delenv("SLACK_ACTIVITY_HOURS")

    def broken(method, **p):
        raise RuntimeError("down")
    monkeypatch.setattr(plugin, "_workspace", ("xoxb-test", SlackWorkspace(broken)))
    monkeypatch.setattr(plugin, "_activity_cache", ActivityCache())
    assert plugin._pre_llm_call(platform="slack") is None


def test_digest_unescapes_slack_entities_and_bare_links():
    m = [msg(KAS, "see <https://api.slack.com/apps> &amp; OAuth &lt;scopes&gt;", 1)]
    digest = format_digest(m, "c", SHACK, NAMES.get, timezone.utc, 24)
    assert digest.endswith("kas: see https://api.slack.com/apps & OAuth <scopes>")
