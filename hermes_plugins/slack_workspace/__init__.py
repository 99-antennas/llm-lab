"""Hermes plugin: Slack workspace tools plus a skill on using them.

Read tools (channel members, channel list) work in any channel Shack can see. Posting and reading
replies to a posted question only work in channels listed in ``SLACK_POST_CHANNELS``
(comma-separated names or IDs); with it unset they refuse every channel.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from .workspace import SlackLookupError, SlackWorkspace, sdk_call_factory

TOOLSET = "slack_workspace"
_SKILL_MD = Path(__file__).parent / "skills" / "slack-workspace" / "SKILL.md"

_lock = threading.Lock()
_workspace: tuple[str, SlackWorkspace] | None = None


def _token() -> str:
    try:
        from agent.secret_scope import get_secret

        return (get_secret("SLACK_BOT_TOKEN") or "").strip()
    except ImportError:  # outside Hermes (tests)
        return os.environ.get("SLACK_BOT_TOKEN", "").strip()


def _post_allowlist() -> set[str]:
    try:
        from agent.secret_scope import get_secret

        raw = get_secret("SLACK_POST_CHANNELS") or ""
    except ImportError:  # outside Hermes (tests)
        raw = os.environ.get("SLACK_POST_CHANNELS", "")
    return {part.strip().lstrip("#").casefold() for part in raw.split(",") if part.strip()}


def _allowed_channel(workspace: SlackWorkspace, ref: str):
    """Resolve ``ref`` (default: current channel) and require it to be on the post allowlist."""
    ref = (ref or "").strip() or _current_slack_channel()
    if not ref:
        raise SlackLookupError("no_channel")
    channel = workspace.resolve_channel(ref)
    allowed = _post_allowlist()
    if channel.id.casefold() not in allowed and channel.name.casefold() not in allowed:
        raise SlackLookupError("channel_not_allowed", detail={
            "channel": channel.name, "allowed_channels": sorted(allowed)})
    return channel


def _get_workspace() -> SlackWorkspace:
    global _workspace
    token = _token()
    if not token:
        raise SlackLookupError("not_authed")
    with _lock:
        if _workspace is None or _workspace[0] != token:
            _workspace = (token, SlackWorkspace(sdk_call_factory(token)))
        return _workspace[1]


def _current_slack_channel() -> str:
    try:
        from gateway.session_context import get_session_env
    except ImportError:
        return ""
    if get_session_env("HERMES_SESSION_PLATFORM", "").strip().lower() != "slack":
        return ""
    return get_session_env("HERMES_SESSION_CHAT_ID", "").strip()


def _available() -> bool:
    try:
        return bool(_token())
    except Exception:  # noqa: BLE001 - check_fn must never raise
        return False


def slack_channel_members(args: dict, **_kwargs) -> str:
    args = args or {}
    channel = str(args.get("channel") or "").strip() or _current_slack_channel()
    if not channel:
        return json.dumps({"error": "no_channel", "hint": "Pass a channel name or ID; "
                           "this conversation is not a Slack channel."})
    try:
        result = _get_workspace().channel_members(channel, include_bots=bool(args.get("include_bots")))
    except SlackLookupError as exc:
        return json.dumps(exc.to_dict())
    return json.dumps(result, ensure_ascii=False)


def slack_list_channels(args: dict, **_kwargs) -> str:
    args = args or {}
    try:
        channels = _get_workspace().list_channels(str(args.get("query") or ""))
    except SlackLookupError as exc:
        return json.dumps(exc.to_dict())
    current = _current_slack_channel()
    return json.dumps({
        "current_channel_id": current or None,
        "channels": [c.to_dict() for c in channels],
    }, ensure_ascii=False)


def slack_post_message(args: dict, **_kwargs) -> str:
    args = args or {}
    mention = args.get("mention")
    if isinstance(mention, str) and mention.strip().lower() != "all":
        mention = [m.strip() for m in mention.split(",") if m.strip()]
    try:
        workspace = _get_workspace()
        channel = _allowed_channel(workspace, str(args.get("channel") or ""))
        result = workspace.post_message(channel, str(args.get("text") or ""),
                                        thread_ts=str(args.get("thread_ts") or ""), mention=mention,
                                        broadcast=str(args.get("broadcast") or ""))
    except SlackLookupError as exc:
        return json.dumps(exc.to_dict(), ensure_ascii=False)
    return json.dumps(result, ensure_ascii=False)


def slack_get_replies(args: dict, **_kwargs) -> str:
    args = args or {}
    ts = str(args.get("ts") or "").strip()
    if not ts:
        return json.dumps({"error": "missing_ts", "hint": "Pass the ts returned by slack_post_message."})
    try:
        workspace = _get_workspace()
        channel = _allowed_channel(workspace, str(args.get("channel") or ""))
        result = workspace.get_replies(channel, ts)
    except SlackLookupError as exc:
        return json.dumps(exc.to_dict(), ensure_ascii=False)
    return json.dumps(result, ensure_ascii=False)


_TOOLS = {
    "slack_channel_members": (
        slack_channel_members,
        "List the people in a Slack channel (names, titles, timezones and <@ID> mention syntax). "
        "Defaults to the current Slack channel. Works for any public channel, and for private "
        "channels, group DMs and DMs that Shack belongs to.",
        {
            "channel": {"type": "string", "description": "Channel ID (C…/G…/D…), #name, or name. "
                        "Omit for the current Slack channel."},
            "include_bots": {"type": "boolean", "description": "Also list bots/apps (default false)."},
        },
    ),
    "slack_list_channels": (
        slack_list_channels,
        "List the Slack channels Shack is a member of (ID, name, public/private, topic, purpose).",
        {"query": {"type": "string", "description": "Optional substring filter on the channel name."}},
    ),
    "slack_post_message": (
        slack_post_message,
        "Post a message to an allowed Slack channel (or reply in a thread), tagging people so they get "
        "notified. Write @Name in the text (names from slack_channel_members) or set mention='all' to "
        "tag everyone in the channel. Set broadcast='channel' (or 'here') for a real @channel/@here; "
        "that is the only way to broadcast. Fails without posting if a name doesn't match a channel member. "
        "Returns the message ts; keep it to collect answers with slack_get_replies.",
        {
            "channel": {"type": "string", "description": "Channel #name or ID. Omit for the current channel."},
            "text": {"type": "string", "description": "Message text (Slack mrkdwn). Use @Name to tag people."},
            "mention": {"description": "'all' to tag every person in the channel, or a list of names to tag.",
                        "anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
            "thread_ts": {"type": "string", "description": "Reply in this thread instead of the channel."},
            "broadcast": {"type": "string", "enum": ["channel", "here"],
                          "description": "Add a real @channel (everyone) or @here (people online). "
                                         "Use only for announcements the whole channel must see."},
        },
        ["text"],
    ),
    "slack_get_replies": (
        slack_get_replies,
        "Collect answers to a message Shack posted: thread replies plus later channel messages from the "
        "people it tagged, and who hasn't answered yet (waiting_on). Only for allowed channels.",
        {
            "ts": {"type": "string", "description": "The ts of the question, from slack_post_message."},
            "channel": {"type": "string", "description": "Channel #name or ID. Omit for the current channel."},
        },
        ["ts"],
    ),
}


def register(ctx) -> None:
    for name, (handler, description, properties, *required) in _TOOLS.items():
        parameters = {"type": "object", "properties": properties}
        if required:
            parameters["required"] = required[0]
        ctx.register_tool(
            name=name,
            toolset=TOOLSET,
            schema={"name": name, "description": description, "parameters": parameters},
            handler=handler,
            check_fn=_available,
            description=description,
            emoji="\U0001f465",  # busts in silhouette
        )
    ctx.register_skill(
        "slack-workspace", _SKILL_MD,
        "Answer who is in a Slack channel and which channels Shack can see.",
    )
