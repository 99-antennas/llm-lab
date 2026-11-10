from datetime import timezone

import pytest

from hermes_plugins.slack_workspace import reactions
from hermes_plugins.slack_workspace.activity import format_digest
from hermes_plugins.slack_workspace.workspace import SlackWorkspace

NAMES = {"U0KAS": "kas", "U0RAY": "Ray", "U0NICK": "Nick", "U0SHACK": "Shack"}


@pytest.mark.parametrize(("name", "meaning"), [
    ("+1", "yes"), ("thumbsup", "yes"), ("+1::skin-tone-2", "yes"), ("white_check_mark", "yes"),
    ("heavy_check_mark", "yes"), ("ballot_box_with_check", "yes"), ("ok_hand", "yes"),
    ("-1", "no"), ("x", "no"), ("eyes", ""), ("joy", ""), ("", ""),
])
def test_meaning(name, meaning):
    assert reactions.meaning(name) == meaning


def test_answers_and_summary():
    message = {"reactions": [{"name": "+1::skin-tone-3", "users": ["U0KAS", "U0RAY"]},
                             {"name": "eyes", "users": ["U0NICK"]},
                             {"name": "x", "users": ["U0RAY"]}]}
    assert reactions.answers(message) == {"U0KAS": ["+1"], "U0RAY": ["+1", "x"]}
    assert reactions.summary(message, NAMES.get) == ":+1: kas, Ray; :eyes: Nick; :x: Ray"
    assert reactions.summary({}, NAMES.get) == ""


def test_digest_shows_reactions():
    m = [{"user": "U0SHACK", "text": "Book the Mendocino house?", "ts": "1800000000.000000",
          "reactions": [{"name": "white_check_mark", "users": ["U0KAS"]}]}]
    digest = format_digest(m, "c", "U0SHACK", NAMES.get, timezone.utc, 24)
    assert digest.endswith("Shack (you): Book the Mendocino house? (reactions: :white_check_mark: kas)")
    assert ":+1: or :white_check_mark: reaction means yes" in digest.splitlines()[0]


def test_get_replies_counts_yes_no_reactions_not_eyes():
    question = {"ts": "100.0", "user": "U0SHACK", "text": "<@U0KAS> <@U0RAY> <@U0NICK> Feb 12–15 ok?",
                "reactions": [{"name": "+1", "users": ["U0KAS"]}, {"name": "x", "users": ["U0RAY"]},
                              {"name": "eyes", "users": ["U0NICK"]}]}

    def call(method, **p):
        if method == "auth.test":
            return {"user_id": "U0SHACK"}
        if method == "conversations.replies":
            return {"messages": [question]}
        if method == "conversations.history":
            return {"messages": []}
        if method == "users.list":
            return {"members": [{"id": u, "name": n, "profile": {"display_name": n}} for u, n in NAMES.items()]}
        if method == "conversations.info":
            return {"channel": {"id": "C1", "name": "retreat-planning"}}
        raise AssertionError(method)

    ws = SlackWorkspace(call)
    out = ws.get_replies(ws.resolve_channel("C0RETREAT"), "100.0")
    assert [(r["name"], r["reaction"], r["meaning"], r["where"]) for r in out["responses"]] == [
        ("kas", ":+1:", "yes", "reaction"), ("Ray", ":x:", "no", "reaction")]
    assert out["waiting_on"] == ["Nick"]
    assert out["reactions"] == ":+1: kas; :x: Ray; :eyes: Nick"
