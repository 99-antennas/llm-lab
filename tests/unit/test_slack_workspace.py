import json

import pytest

import hermes_plugins.slack_workspace as plugin
from hermes_plugins.slack_workspace.workspace import MAX_MEMBERS, SlackLookupError, SlackWorkspace

USERS = {
    "U01RAY": {"id": "U01RAY", "name": "ray.j", "tz": "America/New_York",
               "profile": {"display_name": "Ray", "real_name": "Ray Johnson", "title": "Chef"}},
    "U02KAS": {"id": "U02KAS", "name": "kas", "profile": {"display_name": "", "real_name": "Kas Stohr"}},
    "U03BOT": {"id": "U03BOT", "name": "deploybot", "is_bot": True, "profile": {"real_name": "Deploy Bot"}},
    "U04OLD": {"id": "U04OLD", "name": "old", "deleted": True, "profile": {"real_name": "Old Timer"}},
}
CHANNELS = {
    "C0RETREAT": {"id": "C0RETREAT", "name": "retreat-planning", "is_private": False, "num_members": 3},
    "G0SECRET": {"id": "G0SECRET", "name": "secret-stuff", "is_private": True, "num_members": 2},
}
PUBLIC_NOT_JOINED = {"id": "C0RANDOM", "name": "random", "is_private": False, "is_member": False}
MEMBERS = {"C0RETREAT": ["U02KAS", "U01RAY", "U03BOT", "U04OLD"], "G0SECRET": ["U02KAS"],
           "C0RANDOM": ["U01RAY", "U09NEW"]}


class FakeSlack:
    def __init__(self, mpim_scope=True, users_list_fails=False, page_size=None):
        self.calls = []
        self.mpim_scope = mpim_scope
        self.users_list_fails = users_list_fails
        self.page_size = page_size
        self.posted = []
        self.thread = []
        self.history = []

    def _page(self, items, key, cursor):
        if not self.page_size:
            return {"ok": True, key: items}
        start = int(cursor or 0)
        end = start + self.page_size
        nxt = str(end) if end < len(items) else ""
        return {"ok": True, key: items[start:end], "response_metadata": {"next_cursor": nxt}}

    def __call__(self, method, **params):
        self.calls.append((method, params))
        cursor = params.get("cursor")
        if method == "users.conversations":
            if "mpim" in params["types"] and not self.mpim_scope:
                raise SlackLookupError("missing_scope", "mpim:read")
            return self._page(list(CHANNELS.values()), "channels", cursor)
        if method == "conversations.list":
            return self._page(list(CHANNELS.values()) + [PUBLIC_NOT_JOINED], "channels", cursor)
        if method == "conversations.info":
            data = CHANNELS.get(params["channel"]) or (
                PUBLIC_NOT_JOINED if params["channel"] == "C0RANDOM" else None)
            if not data:
                raise SlackLookupError("channel_not_found")
            return {"ok": True, "channel": data}
        if method == "conversations.members":
            return self._page(MEMBERS[params["channel"]], "members", cursor)
        if method == "users.list":
            if self.users_list_fails:
                raise SlackLookupError("ratelimited")
            return self._page(list(USERS.values()), "members", cursor)
        if method == "auth.test":
            return {"ok": True, "user_id": "U00SHACK"}
        if method == "chat.postMessage":
            self.posted.append(params)
            return {"ok": True, "ts": "1700000100.000100"}
        if method == "conversations.replies":
            return {"ok": True, "messages": self.thread}
        if method == "conversations.history":
            return {"ok": True, "messages": self.history}
        if method == "users.info":
            if params["user"] == "U09NEW":
                return {"ok": True, "user": {"id": "U09NEW", "name": "newbie",
                                             "profile": {"real_name": "New Person"}}}
            raise SlackLookupError("user_not_found")
        raise AssertionError(f"unexpected {method}")


def test_members_of_channel_by_id_excludes_bots_and_deactivated():
    result = SlackWorkspace(FakeSlack()).channel_members("C0RETREAT")
    assert result["channel"]["name"] == "retreat-planning"
    assert result["member_count"] == 2
    assert result["bot_count"] == 1
    assert [m["name"] for m in result["members"]] == ["Kas Stohr", "Ray"]
    ray = result["members"][1]
    assert ray == {"id": "U01RAY", "name": "Ray", "mention": "<@U01RAY>", "real_name": "Ray Johnson",
                   "handle": "ray.j", "title": "Chef", "timezone": "America/New_York"}


def test_include_bots():
    result = SlackWorkspace(FakeSlack()).channel_members("C0RETREAT", include_bots=True)
    assert "Deploy Bot" in [m["name"] for m in result["members"]]


@pytest.mark.parametrize("ref", ["#secret-stuff", "secret-stuff", "Secret-Stuff", "<#G0SECRET|secret-stuff>",
                                 "G0SECRET"])
def test_resolves_channel_references(ref):
    result = SlackWorkspace(FakeSlack()).channel_members(ref)
    assert result["channel"]["id"] == "G0SECRET"
    assert result["channel"]["kind"] == "private_channel"


def test_public_channel_bot_has_not_joined_and_unknown_user_falls_back_to_users_info():
    fake = FakeSlack()
    result = SlackWorkspace(fake).channel_members("#random")
    assert result["channel"]["shack_is_member"] is False
    assert [m["name"] for m in result["members"]] == ["New Person", "Ray"]
    assert ("users.info", {"user": "U09NEW"}) in fake.calls


def test_unknown_channel_name_raises():
    with pytest.raises(SlackLookupError) as exc:
        SlackWorkspace(FakeSlack()).channel_members("#nope")
    assert exc.value.to_dict()["error"] == "channel_not_found"
    assert "hint" in exc.value.to_dict()


def test_pagination_follows_cursors():
    result = SlackWorkspace(FakeSlack(page_size=1)).channel_members("C0RETREAT", include_bots=True)
    assert result["member_count"] + result["bot_count"] == 3


def test_list_channels_falls_back_without_mpim_scope():
    fake = FakeSlack(mpim_scope=False)
    ws = SlackWorkspace(fake)
    assert [c.name for c in ws.list_channels()] == ["retreat-planning", "secret-stuff"]
    ws.list_channels()
    types = [p["types"] for m, p in fake.calls if m == "users.conversations"]
    assert types == ["public_channel,private_channel,mpim", "public_channel,private_channel",
                     "public_channel,private_channel"]


def test_list_channels_query_filter():
    assert [c.name for c in SlackWorkspace(FakeSlack()).list_channels("#retreat")] == ["retreat-planning"]


def test_user_directory_is_cached_until_ttl():
    now = [0.0]
    fake = FakeSlack()
    ws = SlackWorkspace(fake, ttl_seconds=60, clock=lambda: now[0])
    ws.channel_members("C0RETREAT")
    ws.channel_members("C0RETREAT")
    assert sum(1 for m, _ in fake.calls if m == "users.list") == 1
    now[0] = 61
    ws.channel_members("C0RETREAT")
    assert sum(1 for m, _ in fake.calls if m == "users.list") == 2


def test_users_list_failure_falls_back_to_ids():
    result = SlackWorkspace(FakeSlack(users_list_fails=True)).channel_members("G0SECRET")
    assert result["members"] == [{"id": "U02KAS", "name": "U02KAS", "mention": "<@U02KAS>"}]


def test_member_list_is_capped(monkeypatch):
    big = [f"U{i:06d}" for i in range(MAX_MEMBERS + 5)]
    monkeypatch.setitem(MEMBERS, "C0RETREAT", big)
    fake = FakeSlack()
    result = SlackWorkspace(lambda m, **p: {"ok": True, "user": {"id": p["user"]}} if m == "users.info"
                            else fake(m, **p)).channel_members("C0RETREAT")
    assert len(result["members"]) == MAX_MEMBERS
    assert result["truncated"] is True


# -- plugin wiring ------------------------------------------------------------------------------


@pytest.fixture
def wired(monkeypatch):
    fake = FakeSlack()
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setattr(plugin, "_workspace", ("xoxb-test", SlackWorkspace(fake)))
    return fake


def test_tool_defaults_to_current_channel(wired, monkeypatch):
    monkeypatch.setattr(plugin, "_current_slack_channel", lambda: "C0RETREAT")
    out = json.loads(plugin.slack_channel_members({}))
    assert out["channel"]["id"] == "C0RETREAT"


def test_tool_without_channel_outside_slack(wired, monkeypatch):
    monkeypatch.setattr(plugin, "_current_slack_channel", lambda: "")
    assert json.loads(plugin.slack_channel_members({}))["error"] == "no_channel"


def test_tool_reports_slack_errors(wired):
    out = json.loads(plugin.slack_channel_members({"channel": "#nope"}))
    assert out["error"] == "channel_not_found"


def test_tool_without_token(monkeypatch):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    assert json.loads(plugin.slack_list_channels({}))["error"] == "not_authed"
    assert plugin._available() is False


def test_list_channels_tool(wired, monkeypatch):
    monkeypatch.setattr(plugin, "_current_slack_channel", lambda: "C0RETREAT")
    out = json.loads(plugin.slack_list_channels({"query": "secret"}))
    assert out["current_channel_id"] == "C0RETREAT"
    assert [c["name"] for c in out["channels"]] == ["secret-stuff"]


def test_register_registers_tools_and_skill():
    class Ctx:
        def __init__(self):
            self.tools, self.skills, self.hooks = {}, {}, {}

        def register_tool(self, **kw):
            self.tools[kw["name"]] = kw

        def register_hook(self, name, callback):
            self.hooks[name] = callback

        def register_skill(self, name, path, description=""):
            assert path.exists()
            self.skills[name] = path

    ctx = Ctx()
    plugin.register(ctx)
    assert set(ctx.tools) == {"slack_channel_members", "slack_list_channels", "slack_post_message",
                              "slack_get_replies", "slack_bot_manifest"}
    assert ctx.tools["slack_bot_manifest"]["check_fn"]() is True
    assert ctx.tools["slack_post_message"]["schema"]["parameters"]["required"] == ["text"]
    assert all(t["toolset"] == "slack_workspace" for t in ctx.tools.values())
    assert set(ctx.skills) == {"slack-workspace", "slack-bot-manifest"}
    assert set(ctx.hooks) == {"pre_gateway_dispatch", "pre_llm_call"}


# -- posting and collecting replies -------------------------------------------------------------


def _channel(ws, ref="C0RETREAT"):
    return ws.resolve_channel(ref)


def test_post_converts_at_names_to_tags():
    fake = FakeSlack()
    ws = SlackWorkspace(fake)
    out = ws.post_message(_channel(ws), "Hey @Ray and @Kas Stohr, which weekend works?")
    assert fake.posted[0]["text"] == "Hey <@U01RAY> and <@U02KAS>, which weekend works?"
    assert fake.posted[0]["channel"] == "C0RETREAT"
    assert out["tagged"] == ["Ray", "Kas Stohr"]
    assert out["ts"] == out["thread_ts"] == "1700000100.000100"


def test_post_mention_all_tags_every_person_but_not_bots_or_deactivated():
    fake = FakeSlack()
    ws = SlackWorkspace(fake)
    ws.post_message(_channel(ws), "Dates?", mention="all")
    assert fake.posted[0]["text"] == "<@U02KAS> <@U01RAY> Dates?"


def test_post_mention_list_and_no_duplicate_tags():
    fake = FakeSlack()
    ws = SlackWorkspace(fake)
    ws.post_message(_channel(ws), "@Ray, dates?", mention=["Ray", "kas"])
    assert fake.posted[0]["text"] == "<@U02KAS> <@U01RAY>, dates?"


def test_post_refuses_unknown_names_and_posts_nothing():
    fake = FakeSlack()
    ws = SlackWorkspace(fake)
    with pytest.raises(SlackLookupError) as exc:
        ws.post_message(_channel(ws), "@Rayna can you help?")
    err = exc.value.to_dict()
    assert err["error"] == "unknown_members"
    assert err["unresolved"] == ["@Rayna"]
    assert err["channel_members"] == ["Kas Stohr", "Ray"]
    assert fake.posted == []


def test_post_refuses_tag_for_non_member():
    fake = FakeSlack()
    ws = SlackWorkspace(fake)
    with pytest.raises(SlackLookupError):
        ws.post_message(_channel(ws, "G0SECRET"), "<@U01RAY> hi")
    assert fake.posted == []


def test_post_leaves_code_emails_and_broadcasts_alone():
    fake = FakeSlack()
    ws = SlackWorkspace(fake)
    ws.post_message(_channel(ws), "@here ping `@Ray` at ray@example.com, @Ray")
    assert fake.posted[0]["text"] == "@here ping `@Ray` at ray@example.com, <@U01RAY>"


def test_post_in_thread():
    fake = FakeSlack()
    ws = SlackWorkspace(fake)
    out = ws.post_message(_channel(ws), "@Ray still need your answer", thread_ts="1700000000.000001")
    assert fake.posted[0]["thread_ts"] == "1700000000.000001"
    assert out["thread_ts"] == "1700000000.000001"


def test_get_replies_collects_thread_and_channel_answers_and_waiting_on():
    fake = FakeSlack()
    fake.thread = [
        {"ts": "100.0", "user": "U00SHACK", "text": "<@U02KAS> <@U01RAY> Which weekend?"},
        {"ts": "101.0", "thread_ts": "100.0", "user": "U02KAS", "text": "Mar 6"},
        {"ts": "102.0", "thread_ts": "100.0", "user": "U00SHACK", "text": "Thanks!"},
    ]
    fake.history = [
        {"ts": "103.0", "user": "U01RAY", "text": "13th for me"},
        {"ts": "104.0", "user": "U09NEW", "text": "unrelated chatter"},
    ]
    out = SlackWorkspace(fake).get_replies(SlackWorkspace(fake).resolve_channel("C0RETREAT"), "100.0")
    assert out["asked"] == ["Kas Stohr", "Ray"]
    assert [(r["name"], r["text"], r["where"]) for r in out["responses"]] == [
        ("Kas Stohr", "Mar 6", "thread"), ("Ray", "13th for me", "channel")]
    assert out["waiting_on"] == []


def test_get_replies_waiting_on():
    fake = FakeSlack()
    fake.thread = [{"ts": "100.0", "user": "U00SHACK", "text": "<@U02KAS> <@U01RAY> Which weekend?"},
                   {"ts": "101.0", "thread_ts": "100.0", "user": "U02KAS", "text": "Mar 6"}]
    ws = SlackWorkspace(fake)
    assert ws.get_replies(ws.resolve_channel("C0RETREAT"), "100.0")["waiting_on"] == ["Ray"]


def test_post_tool_enforces_allowlist(wired, monkeypatch):
    monkeypatch.delenv("SLACK_POST_CHANNELS", raising=False)
    out = json.loads(plugin.slack_post_message({"channel": "#retreat-planning", "text": "hi"}))
    assert out["error"] == "channel_not_allowed"
    monkeypatch.setenv("SLACK_POST_CHANNELS", "secret-stuff")
    out = json.loads(plugin.slack_post_message({"channel": "#retreat-planning", "text": "hi"}))
    assert out["error"] == "channel_not_allowed"
    assert out["allowed_channels"] == ["secret-stuff"]
    assert wired.posted == []


@pytest.mark.parametrize("allow", ["retreat-planning", "#Retreat-Planning", "C0RETREAT", "x, retreat-planning"])
def test_post_tool_allowed_by_name_or_id(wired, monkeypatch, allow):
    monkeypatch.setenv("SLACK_POST_CHANNELS", allow)
    monkeypatch.setattr(plugin, "_current_slack_channel", lambda: "C0RETREAT")
    out = json.loads(plugin.slack_post_message({"text": "Dates? @Ray", "mention": "all"}))
    assert out["ok"] is True
    assert wired.posted[0]["text"] == "<@U02KAS> Dates? <@U01RAY>"


def test_post_tool_mention_comma_string(wired, monkeypatch):
    monkeypatch.setenv("SLACK_POST_CHANNELS", "retreat-planning")
    out = json.loads(plugin.slack_post_message({"channel": "C0RETREAT", "text": "Dates?", "mention": "Ray, kas"}))
    assert out["tagged"] == ["Ray", "Kas Stohr"]


def test_get_replies_tool_requires_ts_and_allowlist(wired, monkeypatch):
    assert json.loads(plugin.slack_get_replies({"channel": "C0RETREAT"}))["error"] == "missing_ts"
    monkeypatch.delenv("SLACK_POST_CHANNELS", raising=False)
    out = json.loads(plugin.slack_get_replies({"channel": "C0RETREAT", "ts": "1.0"}))
    assert out["error"] == "channel_not_allowed"


# -- broadcasts ---------------------------------------------------------------------------------


def test_broadcast_channel_is_prefixed():
    fake = FakeSlack()
    ws = SlackWorkspace(fake)
    out = ws.post_message(_channel(ws), "Retreat dates are locked!", broadcast="channel")
    assert fake.posted[0]["text"] == "<!channel> Retreat dates are locked!"
    assert fake.posted[0]["link_names"] is False
    assert out["broadcast"] == "channel"


def test_broadcast_reuses_plain_keyword_in_text():
    fake = FakeSlack()
    ws = SlackWorkspace(fake)
    ws.post_message(_channel(ws), "Hey @here, quick poll. cc @Ray", broadcast="@here")
    assert fake.posted[0]["text"] == "Hey <!here>, quick poll. cc <@U01RAY>"


def test_broadcast_with_mentions_puts_broadcast_first():
    fake = FakeSlack()
    ws = SlackWorkspace(fake)
    ws.post_message(_channel(ws), "Dates?", mention=["Ray"], broadcast="channel")
    assert fake.posted[0]["text"] == "<!channel> <@U01RAY> Dates?"


@pytest.mark.parametrize(("raw", "plain"), [
    ("<!channel>", "@channel"), ("<!here>", "@here"), ("<!everyone>", "@everyone"),
    ("<!here|here>", "@here"), ("<!subteam^S0DESIGN|@design>", "@design"), ("<!subteam^S0DESIGN>", "@group"),
])
def test_raw_broadcast_syntax_is_defused_without_option(raw, plain):
    fake = FakeSlack()
    ws = SlackWorkspace(fake)
    out = ws.post_message(_channel(ws), f"{raw} dates?")
    assert fake.posted[0]["text"] == f"{plain} dates?"
    assert "<!" not in fake.posted[0]["text"]
    assert out["broadcast"] is None


def test_plain_at_channel_without_option_stays_text():
    fake = FakeSlack()
    ws = SlackWorkspace(fake)
    ws.post_message(_channel(ws), "@channel dates?")
    assert fake.posted[0]["text"] == "@channel dates?"
    assert fake.posted[0]["link_names"] is False


def test_raw_broadcast_defused_even_when_other_broadcast_requested():
    fake = FakeSlack()
    ws = SlackWorkspace(fake)
    ws.post_message(_channel(ws), "<!channel> FYI", broadcast="here")
    assert fake.posted[0]["text"] == "<!here> @channel FYI"


def test_invalid_broadcast_refused():
    fake = FakeSlack()
    ws = SlackWorkspace(fake)
    with pytest.raises(SlackLookupError) as exc:
        ws.post_message(_channel(ws), "hi", broadcast="everyone")
    assert exc.value.code == "invalid_broadcast"
    assert fake.posted == []


def test_get_replies_after_broadcast_tracks_whole_channel():
    fake = FakeSlack()
    fake.thread = [{"ts": "100.0", "user": "U00SHACK", "text": "<!channel> Which weekend?"},
                   {"ts": "101.0", "thread_ts": "100.0", "user": "U01RAY", "text": "13th"}]
    ws = SlackWorkspace(fake)
    out = ws.get_replies(ws.resolve_channel("C0RETREAT"), "100.0")
    assert out["broadcast"] == "channel"
    assert out["asked"] == ["Kas Stohr", "Ray"]
    assert out["waiting_on"] == ["Kas Stohr"]


def test_post_tool_passes_broadcast(wired, monkeypatch):
    monkeypatch.setenv("SLACK_POST_CHANNELS", "retreat-planning")
    out = json.loads(plugin.slack_post_message({"channel": "C0RETREAT", "text": "Locked in!",
                                                 "broadcast": "channel"}))
    assert out["broadcast"] == "channel"
    assert wired.posted[0]["text"] == "<!channel> Locked in!"
    out = json.loads(plugin.slack_post_message({"channel": "#local-yocal", "text": "x", "broadcast": "channel"}))
    assert out["error"] in {"channel_not_allowed", "channel_not_found"}
