import pytest

from hermes_scripts import slack_tag_reminders as rem
from hermes_plugins.slack_workspace.workspace import SlackLookupError

HOUR = 3600.0
NOW = 1_800_000_000.0
SHACK, KAS, RAY, NICK, BOT = "U00SHACK", "U02KAS", "U01RAY", "U03NICK", "U04BOT"


def ts(hours_ago: float, seq: int = 0) -> str:
    return f"{NOW - hours_ago * HOUR:.6f}"[:-1] + str(seq)


def msg(user, text, hours_ago, **extra):
    return {"user": user, "text": text, "ts": ts(hours_ago), **extra}


def overdue(top, threads=None, after=24, lookback=72):
    return rem.find_overdue("C0RETREAT", top, threads or {}, SHACK, NOW, after * HOUR, lookback * 24 * HOUR / 24,
                            lambda u: u != BOT)


@pytest.mark.parametrize(("text", "expected"), [
    ("<@U01RAY> can you book it?", ["U01RAY"]),
    ("  <@U01RAY|ray> can you?", ["U01RAY"]),
    ("<@U01RAY> <@U03NICK>, thoughts?", ["U01RAY", "U03NICK"]),
    ("<@U01RAY>: <@U01RAY> twice", ["U01RAY"]),
    ("Hey <@U01RAY> can you?", []),
    ("<!channel> anyone?", []),
    ("", []),
])
def test_leading_tags(text, expected):
    assert rem.leading_tags(text) == expected


def test_unanswered_leading_tag_after_a_day_is_due():
    top = [msg(KAS, "<@U01RAY> can you book the cabin?", 25)]
    [r] = overdue(top)
    assert r.user_ids == (RAY,)
    assert r.author_id == KAS
    assert r.thread_ts == r.message_ts == top[0]["ts"]


def test_not_due_before_a_day():
    assert overdue([msg(KAS, "<@U01RAY> can you book the cabin?", 23)]) == []


def test_not_due_beyond_lookback():
    assert overdue([msg(KAS, "<@U01RAY> can you book the cabin?", 80)]) == []


def test_tag_not_at_start_is_ignored():
    assert overdue([msg(KAS, "Can <@U01RAY> book the cabin?", 30)]) == []


def test_thread_reply_counts_as_response():
    root = msg(KAS, "<@U01RAY> can you book the cabin?", 30, reply_count=1)
    threads = {root["ts"]: [root, msg(RAY, "on it", 29, thread_ts=root["ts"])]}
    assert overdue([root], threads) == []


def test_later_channel_message_counts_as_response():
    top = [msg(RAY, "booked!", 26), msg(KAS, "<@U01RAY> can you book the cabin?", 30)]
    assert overdue(top) == []


def test_earlier_channel_message_does_not_count():
    top = [msg(KAS, "<@U01RAY> can you book the cabin?", 30), msg(RAY, "morning all", 31)]
    assert len(overdue(top)) == 1


def test_reaction_counts_as_response():
    top = [msg(KAS, "<@U01RAY> can you book the cabin?", 30,
               reactions=[{"name": "white_check_mark", "users": [RAY]}])]
    assert overdue(top) == []


def test_someone_elses_reply_does_not_count():
    root = msg(KAS, "<@U01RAY> can you book the cabin?", 30, reply_count=1)
    threads = {root["ts"]: [root, msg(NICK, "I can if Ray can't", 29, thread_ts=root["ts"])]}
    assert len(overdue([root], threads)) == 1


def test_reminded_only_once():
    root = msg(KAS, "<@U01RAY> can you book the cabin?", 30, reply_count=1)
    threads = {root["ts"]: [root, msg(SHACK, "<@U01RAY> friendly reminder", 5, thread_ts=root["ts"])]}
    assert overdue([root], threads) == []


def test_multiple_tags_remind_only_those_still_silent():
    root = msg(KAS, "<@U01RAY> <@U03NICK> which weekend?", 30, reply_count=1)
    threads = {root["ts"]: [root, msg(NICK, "13th", 29, thread_ts=root["ts"])]}
    [r] = overdue([root], threads)
    assert r.user_ids == (RAY,)


def test_tag_inside_thread_reminds_in_that_thread():
    root = msg(KAS, "Cabin options", 40, reply_count=2)
    reply = msg(NICK, "<@U01RAY> which one do you prefer?", 30, thread_ts=root["ts"])
    reply["ts"] = ts(30, 1)
    threads = {root["ts"]: [root, reply]}
    [r] = overdue([root], threads)
    assert r.thread_ts == root["ts"]
    assert r.message_ts == reply["ts"]
    assert r.author_id == NICK


@pytest.mark.parametrize("message", [
    msg(SHACK, "<@U01RAY> which weekend?", 30),                         # Shack's own question
    msg(KAS, "<@U00SHACK> summarize please", 30),                       # addressed to Shack
    msg(KAS, "<@U02KAS> note to self", 30),                             # self-tag
    msg(KAS, "<@U04BOT> deploy", 30),                                   # bot
    msg(KAS, "<@U01RAY> hi", 30, subtype="channel_join"),               # system message
    {"bot_id": "B1", "user": NICK, "text": "<@U01RAY> hi", "ts": ts(30)},  # bot post
])
def test_skipped_messages(message):
    assert overdue([message]) == []


def test_reminder_text():
    r = rem.Reminder("C0RETREAT", "1.0", "1.0", KAS, (RAY, NICK))
    text = rem.reminder_text(r, "https://x.slack.com/archives/C0RETREAT/p1")
    assert text.startswith("<@U01RAY> <@U03NICK> friendly reminder: <@U02KAS> is waiting")
    assert "<https://x.slack.com/archives/C0RETREAT/p1|this message>" in text
    assert "the message above" in rem.reminder_text(r)


class FakeSlack:
    def __init__(self, history, threads=None):
        self.history, self.threads = history, threads or {}
        self.posted = []

    def __call__(self, method, **p):
        if method == "auth.test":
            return {"user_id": SHACK}
        if method == "conversations.info":
            return {"channel": {"id": p["channel"], "name": "retreat-planning", "is_private": True}}
        if method == "conversations.history":
            assert float(p["oldest"]) == pytest.approx(NOW - 3 * 86400)
            return {"messages": self.history}
        if method == "conversations.replies":
            return {"messages": self.threads[p["ts"]]}
        if method == "users.info":
            if p["user"] == BOT:
                return {"user": {"id": BOT, "is_bot": True}}
            if p["user"] == "U09GONE":
                raise SlackLookupError("user_not_found")
            return {"user": {"id": p["user"]}}
        if method == "chat.getPermalink":
            return {"permalink": f"https://x.slack.com/p{p['message_ts']}"}
        if method == "chat.postMessage":
            self.posted.append(p)
            return {"ts": "9.9"}
        raise AssertionError(method)


def test_run_posts_reminders_in_thread():
    root = msg(KAS, "<@U01RAY> <@U09GONE> can you book the cabin?", 30)
    fake = FakeSlack([root, msg(NICK, "<@U04BOT> deploy", 30)])
    sent = rem.run(fake, ["C0RETREAT"], NOW, after_hours=24, lookback_days=3)
    assert len(sent) == 1 and "U01RAY" in sent[0]
    [post] = fake.posted
    assert post["thread_ts"] == root["ts"]
    assert post["text"].startswith("<@U01RAY> friendly reminder: <@U02KAS>")
    assert post["link_names"] is False


def test_run_dry_run_posts_nothing():
    fake = FakeSlack([msg(KAS, "<@U01RAY> can you book the cabin?", 30)])
    sent = rem.run(fake, ["C0RETREAT"], NOW, after_hours=24, lookback_days=3, dry_run=True)
    assert sent and sent[0].endswith("(dry run)")
    assert fake.posted == []


def test_main_without_channels_is_silent(monkeypatch, capsys):
    monkeypatch.delenv("SLACK_REMINDER_CHANNELS", raising=False)
    monkeypatch.delenv("SLACK_POST_CHANNELS", raising=False)
    assert rem.main([]) == 0
    assert capsys.readouterr().out == ""


def test_token_falls_back_to_hermes_env_file(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("OTHER=1\nSLACK_BOT_TOKEN='xoxb-file'\n")
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.setattr(rem, "HERMES_HOME", tmp_path)
    monkeypatch.setattr(rem, "S6_ENV_DIR", tmp_path / "missing")
    assert rem._token() == "xoxb-file"


def test_token_prefers_s6_container_env(monkeypatch, tmp_path):
    (tmp_path / "SLACK_BOT_TOKEN").write_text("xoxb-s6\n")
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.setattr(rem, "S6_ENV_DIR", tmp_path)
    assert rem._token() == "xoxb-s6"


@pytest.mark.parametrize(("emoji", "counts"), [
    ("+1", True), ("+1::skin-tone-4", True), ("white_check_mark", True), ("heavy_check_mark", True),
    ("-1", True), ("x", True), ("eyes", False), ("joy", False),
])
def test_only_answer_reactions_count(emoji, counts):
    top = [msg(KAS, "<@U01RAY> can you book the cabin?", 30, reactions=[{"name": emoji, "users": [RAY]}])]
    assert (overdue(top) == []) is counts
