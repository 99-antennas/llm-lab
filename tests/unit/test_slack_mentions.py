import pytest

import hermes_plugins.slack_mentions as plugin
from hermes_plugins.slack_mentions.mentions import (
    MemberDirectory,
    MemberIndex,
    SlackMember,
    convert_mentions,
    fetch_members,
    roster_prompt,
)

RAY = SlackMember("U01RAY", "ray.j", "Ray", "Ray Johnson", False)
KAS = SlackMember("U02KAS", "kas", "kas", "Kas Stohr", False)
RAYNA = SlackMember("U03RNA", "rayna", "Rayna", "Rayna Lee", False)
DEPLOYBOT = SlackMember("U04BOT", "deploybot", "", "Deploy Bot", True)


@pytest.fixture
def index():
    return MemberIndex([RAY, KAS, RAYNA, DEPLOYBOT])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hey @Ray, can you look?", "Hey <@U01RAY>, can you look?"),
        ("@ray.j please review", "<@U01RAY> please review"),
        ("cc @Ray Johnson.", "cc <@U01RAY>."),
        ("that's @Ray's call", "that's <@U01RAY>'s call"),
        ("@Deploy Bot run it", "<@U04BOT> run it"),
        ("@Kas Stohr and @Rayna", "<@U02KAS> and <@U03RNA>"),
        ("(@ray)", "(<@U01RAY>)"),
    ],
)
def test_converts_names_to_slack_mentions(index, text, expected):
    assert convert_mentions(text, index) == expected


@pytest.mark.parametrize(
    "text",
    [
        "mail ray@example.com",
        "see `@Ray` in code",
        "```\nping @Ray\n```",
        "already <@U01RAY>",
        "link https://x.com/@ray",
        "@here and @channel",
        "@Nobody is home",
        "@@Ray",
    ],
)
def test_leaves_non_mentions_alone(index, text):
    assert convert_mentions(text, index) == text


def test_ambiguous_first_name_is_not_converted():
    ray_j = SlackMember("U01RAY", "ray.j", "", "Ray Johnson", False)
    index = MemberIndex([ray_j, SlackMember("U09RAY", "ray.k", "", "Ray Kim", False)])
    assert convert_mentions("@Ray hi", index) == "@Ray hi"
    assert convert_mentions("@Ray Kim hi", index) == "<@U09RAY> hi"


def test_exact_name_beats_another_members_first_name():
    ray_j = SlackMember("U01RAY", "ray.j", "", "Ray Johnson", False)
    index = MemberIndex([ray_j, SlackMember("U09RAY", "ray", "Ray", "", False)])
    assert convert_mentions("@Ray", index) == "<@U09RAY>"


def test_duplicate_display_names_are_ambiguous():
    index = MemberIndex([RAY, SlackMember("U09RAY", "ray.k", "Ray", "Ray Kim", False)])
    assert convert_mentions("@Ray", index) == "@Ray"
    assert convert_mentions("@Ray Kim", index) == "<@U09RAY>"


def test_mention_name_does_not_span_lines(index):
    assert convert_mentions("@Ray\nJohnson", index) == "<@U01RAY>\nJohnson"


def test_roster_prompt_lists_members_and_bots(index):
    prompt = roster_prompt(index)
    assert "Ray (Ray Johnson)" in prompt
    assert "Deploy Bot [bot]" in prompt
    assert roster_prompt(MemberIndex([])) == ""


def test_fetch_members_paginates_and_skips_self_deleted_and_slackbot():
    pages = {
        "": {
            "members": [
                {
                    "id": "U01RAY",
                    "name": "ray.j",
                    "profile": {"display_name": "Ray", "real_name": "Ray Johnson"},
                },
                {"id": "USHACK", "name": "shack", "is_bot": True, "profile": {}},
                {"id": "USLACKBOT", "name": "slackbot", "profile": {}},
            ],
            "response_metadata": {"next_cursor": "p2"},
        },
        "p2": {
            "members": [
                {"id": "U05OLD", "name": "old", "deleted": True, "profile": {}},
                {
                    "id": "U04BOT",
                    "name": "deploybot",
                    "is_bot": True,
                    "profile": {"real_name": "Deploy Bot"},
                },
            ],
            "response_metadata": {"next_cursor": ""},
        },
    }

    def call(token, method, params=None):
        assert token == "xoxb-test"
        if method == "auth.test":
            return {"ok": True, "user_id": "USHACK"}
        return pages[params.get("cursor", "")]

    members = fetch_members("xoxb-test", call=call)
    assert [m.user_id for m in members] == ["U01RAY", "U04BOT"]
    assert members[1].is_bot


def test_directory_caches_and_keeps_last_good_index_on_failure():
    now = [0.0]
    calls = []

    def fetch(token):
        calls.append(token)
        if len(calls) > 1:
            raise RuntimeError("slack down")
        return [RAY]

    directory = MemberDirectory(
        lambda: "xoxb", ttl_seconds=60, fetch=fetch, clock=lambda: now[0]
    )
    assert directory.get().lookup("ray") == "U01RAY"
    assert directory.get().lookup("ray") == "U01RAY"
    assert len(calls) == 1

    now[0] = 120
    directory._refresh()  # what the background thread runs
    assert len(calls) == 2
    assert directory.get().lookup("ray") == "U01RAY"


def test_directory_without_token_is_empty():
    directory = MemberDirectory(
        lambda: "", fetch=lambda token: pytest.fail("should not fetch")
    )
    assert directory.get().members == []


def test_hooks_only_apply_to_slack(monkeypatch, index):
    monkeypatch.setattr(plugin._directory, "get", lambda: index)
    assert (
        plugin._transform_llm_output(response_text="hi @Ray", platform="slack")
        == "hi <@U01RAY>"
    )
    assert (
        plugin._transform_llm_output(response_text="hi @Ray", platform="telegram")
        is None
    )
    assert (
        plugin._transform_llm_output(response_text="no mentions", platform="slack")
        is None
    )
    assert "Workspace members" in plugin._pre_llm_call(platform="slack")["context"]
    assert plugin._pre_llm_call(platform="api_server") is None


def test_register_wires_both_hooks():
    registered = {}

    class Ctx:
        def register_hook(self, name, callback):
            registered[name] = callback

    plugin.register(Ctx())
    assert set(registered) == {"transform_llm_output", "pre_llm_call"}
