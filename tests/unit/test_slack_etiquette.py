import asyncio
from types import SimpleNamespace

import pytest

import hermes_plugins.slack_workspace as plugin
from hermes_plugins.slack_workspace.etiquette import continues_addressed_exchange, leading_tags
from hermes_plugins.slack_workspace.workspace import SlackWorkspace

SHACK, KAS, RAY, NICK = "U0B7BC636N6", "U0GEPK3FW", "U0577L3CTT9", "U03NICK"
WINDOW = 600.0


def m(user, text, ts, **extra):
    return {"user": user, "text": text, "ts": f"{ts:.6f}", **extra}


def check(current, *earlier_oldest_first):
    return continues_addressed_exchange(current, list(reversed(earlier_oldest_first)), SHACK, WINDOW)


def test_replay_of_the_retreat_planning_thread():
    """kas tagged Ray in a thread Shack started, then added an untagged follow-up 52s later."""
    root = m(SHACK, "Here's a Slack app manifest for `ray-mclendon-prometheus`", 1794289641.258499)
    tagged = m(KAS, "<@U0577L3CTT9> Looks like prometheus is a bot managed by ChatGPT", 1794289797.280189)
    follow_up = m(KAS, "I may need to enable adding prometheus as a proper bot", 1794289849.492619)
    assert check(follow_up, root, tagged) is True


def test_several_follow_ups_from_sender():
    assert check(m(KAS, "and three", 130), m(KAS, "<@U0577L3CTT9> one", 100), m(KAS, "two", 110))


def test_reply_from_the_tagged_person_and_back_and_forth():
    tagged = m(KAS, "<@U0577L3CTT9> can you book it?", 100)
    assert check(m(RAY, "sure, which dates?", 120), tagged)
    assert check(m(KAS, "the 13th", 140), tagged, m(RAY, "sure, which dates?", 120))


def test_third_person_is_not_part_of_the_exchange():
    assert not check(m(NICK, "what's the plan?", 120), m(KAS, "<@U0577L3CTT9> can you book it?", 100))


def test_third_person_speaking_ends_the_exchange():
    assert not check(m(KAS, "anyway, Shack what's next?", 140),
                     m(KAS, "<@U0577L3CTT9> can you book it?", 100), m(NICK, "I can help", 120))


def test_tagging_shack_always_gets_through():
    assert not check(m(KAS, "<@U0B7BC636N6> what do you think?", 120), m(KAS, "<@U0577L3CTT9> hi", 100))
    assert not check(m(KAS, "what do you think <@U0B7BC636N6|shack>?", 120), m(KAS, "<@U0577L3CTT9> hi", 100))


def test_shack_speaking_ends_the_exchange():
    assert not check(m(KAS, "thanks!", 140), m(KAS, "<@U0577L3CTT9> hi", 100), m(SHACK, "noted", 120))


def test_outside_window_is_a_new_conversation():
    assert not check(m(KAS, "ok what next?", 100 + WINDOW + 1), m(KAS, "<@U0577L3CTT9> hi", 100))


def test_no_addressed_message_nearby():
    assert not check(m(KAS, "what's next?", 140), m(KAS, "hello all", 100), m(RAY, "hi", 120))


def test_message_tagging_shack_earlier_ends_the_exchange():
    assert not check(m(KAS, "and?", 140), m(KAS, "<@U0577L3CTT9> hi", 100),
                     m(KAS, "<@U0B7BC636N6> help Ray out", 120))


def test_message_that_itself_opens_with_a_tag():
    assert check(m(KAS, "<@U0577L3CTT9> ping", 100))
    assert not check(m(KAS, "<@U0B7BC636N6> ping", 100))
    assert not check(m(KAS, "<@U0GEPK3FW> note to self", 100))


def test_bot_messages_break_the_exchange():
    assert not check(m(KAS, "and?", 140), m(KAS, "<@U0577L3CTT9> hi", 100),
                     {"bot_id": "B0PROM", "text": "beep", "ts": "120.000000"})


def test_leading_tags_shared_with_reminders():
    from hermes_scripts import slack_tag_reminders
    assert slack_tag_reminders.leading_tags is leading_tags


# -- hook wiring --------------------------------------------------------------------------------


class FakeSlack:
    def __init__(self, replies=(), history=()):
        self.replies, self.history, self.calls = list(replies), list(history), []

    def __call__(self, method, **p):
        self.calls.append((method, p))
        if method == "auth.test":
            return {"user_id": SHACK}
        if method == "conversations.replies":
            return {"messages": self.replies}
        if method == "conversations.history":
            return {"messages": self.history}
        raise AssertionError(method)


def event(raw, platform="slack"):
    return SimpleNamespace(source=SimpleNamespace(platform=SimpleNamespace(value=platform)), raw_message=raw)


@pytest.fixture
def hooked(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_IGNORE_OTHER_USER_MENTIONS", "true")

    def install(fake):
        monkeypatch.setattr(plugin, "_workspace", ("xoxb-test", SlackWorkspace(fake)))
        return fake
    return install


def run(raw, platform="slack"):
    return asyncio.run(plugin._pre_gateway_dispatch(event=event(raw, platform)))


THREAD = [m(SHACK, "manifest", 1000.0), m(KAS, "<@U0577L3CTT9> look", 1100.0)]


def test_hook_skips_follow_up_in_thread(hooked):
    fake = hooked(FakeSlack(replies=THREAD))
    raw = dict(m(KAS, "one more thing", 1150.0), channel="C0CF5QW6YM6", thread_ts="1000.000000")
    out = run(raw)
    assert out["action"] == "skip"
    [params] = [p for meth, p in fake.calls if meth == "conversations.replies"]
    assert params["ts"] == "1000.000000"
    assert not [meth for meth, _ in fake.calls if meth == "conversations.history"]


def test_hook_uses_channel_history_for_top_level(hooked):
    fake = hooked(FakeSlack(history=[m(KAS, "<@U0577L3CTT9> look", 1100.0)]))
    assert run(dict(m(KAS, "one more thing", 1150.0), channel="C0CF5QW6YM6"))["action"] == "skip"
    assert "conversations.history" in [meth for meth, _ in fake.calls]
    assert "conversations.replies" not in [meth for meth, _ in fake.calls]


def test_hook_allows_when_shack_tagged(hooked):
    hooked(FakeSlack(replies=THREAD))
    raw = dict(m(KAS, "<@U0B7BC636N6> thoughts?", 1150.0), channel="C0CF5QW6YM6", thread_ts="1000.000000")
    assert run(raw) is None


def test_hook_ignores_dms_other_platforms_and_flag_off(hooked, monkeypatch):
    fake = hooked(FakeSlack(history=[m(KAS, "<@U0577L3CTT9> look", 1100.0)]))
    assert run(dict(m(KAS, "more", 1150.0), channel="D0123456")) is None
    assert run(dict(m(KAS, "more", 1150.0), channel="C0CF5QW6YM6"), platform="telegram") is None
    monkeypatch.setenv("SLACK_IGNORE_OTHER_USER_MENTIONS", "false")
    assert run(dict(m(KAS, "more", 1150.0), channel="C0CF5QW6YM6")) is None
    assert fake.calls == []


def test_hook_fails_open(hooked):
    def broken(method, **p):
        raise RuntimeError("slack down")
    hooked(broken)
    assert run(dict(m(KAS, "more", 1150.0), channel="C0CF5QW6YM6")) is None
