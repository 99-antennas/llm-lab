"""Hermes plugin: Slack workspace tools plus a skill on using them.

Read tools (channel members, channel list) work in any channel Shack can see. Posting and reading
replies to a posted question only work in channels listed in ``SLACK_POST_CHANNELS``
(comma-separated names or IDs); with it unset they refuse every channel.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from pathlib import Path

from .activity import ActivityCache, default_tz, format_digest
from .etiquette import continues_addressed_exchange
from . import policy
from .manifest import ManifestError, manifest_package
from .workspace import SlackLookupError, SlackWorkspace, sdk_call_factory

TOOLSET = "slack_workspace"
logger = logging.getLogger(__name__)
_TRUE = {"true", "1", "yes", "on"}
_SKILLS_DIR = Path(__file__).parent / "skills"
_SKILL_MD = _SKILLS_DIR / "slack-workspace" / "SKILL.md"

_lock = threading.Lock()
_workspace: tuple[str, SlackWorkspace] | None = None


def _token() -> str:
    try:
        from agent.secret_scope import get_secret

        return (get_secret("SLACK_BOT_TOKEN") or "").strip()
    except ImportError:  # outside Hermes (tests)
        return os.environ.get("SLACK_BOT_TOKEN", "").strip()


def _setting(name: str) -> str:
    try:
        from agent.secret_scope import get_secret

        return (get_secret(name) or "").strip()
    except ImportError:  # outside Hermes (tests)
        return os.environ.get(name, "").strip()


def _followup_window_seconds() -> float:
    try:
        return float(_setting("SLACK_ADDRESSED_FOLLOWUP_MINUTES") or 10) * 60
    except ValueError:
        return 600.0


def _earlier_messages(workspace: SlackWorkspace, channel: str, ts: str, thread_ts: str,
                      window: float) -> list[dict]:
    """Messages before ``ts`` in the same place (thread or channel top level), newest first."""
    oldest = f"{float(ts) - window:.6f}"
    call = workspace._call
    if thread_ts and thread_ts != ts:
        messages = call("conversations.replies", channel=channel, ts=thread_ts, oldest=oldest,
                        latest=ts, inclusive=False, limit=50).get("messages") or []
    else:
        messages = call("conversations.history", channel=channel, oldest=oldest, latest=ts,
                        inclusive=False, limit=20).get("messages") or []
    earlier = [m for m in messages if float(m.get("ts") or 0) < float(ts)]
    return sorted(earlier, key=lambda m: float(m.get("ts") or 0), reverse=True)


def _is_addressed_followup(raw: dict) -> bool:
    channel, ts, thread_ts = raw.get("channel") or "", raw.get("ts") or "", raw.get("thread_ts") or ""
    workspace = _get_workspace()
    window = _followup_window_seconds()
    earlier = _earlier_messages(workspace, channel, ts, thread_ts, window)
    return continues_addressed_exchange(raw, earlier, workspace._own_user_id(), window)


async def _pre_gateway_dispatch(event=None, **_kwargs):
    """Turn "@Shack help" / "@Shack cool-tools" into the /cool-tools command, and drop follow-ups
    in an exchange addressed to someone else (see etiquette.py). Fails open."""
    source = getattr(event, "source", None)
    platform = getattr(getattr(source, "platform", None), "value", getattr(source, "platform", ""))
    raw = getattr(event, "raw_message", None)
    if str(platform or "").lower() != "slack" or not isinstance(raw, dict):
        return None
    if policy.is_tools_request(getattr(event, "text", "") or ""):
        # Hermes can't give a plugin a native Slack slash command (its listener only covers its own
        # 50 built-ins), so plain-text asks are rewritten into the command before dispatch.
        return {"action": "rewrite", "text": "/cool-tools"}
    if _setting("SLACK_IGNORE_OTHER_USER_MENTIONS").lower() not in _TRUE:
        return None
    channel = raw.get("channel") or ""
    if not channel or channel.startswith("D") or not raw.get("ts") or not raw.get("user"):
        return None  # DMs are always for Shack
    try:
        skip = await asyncio.to_thread(_is_addressed_followup, raw)
    except Exception as exc:  # noqa: BLE001 - never block a message because Slack lookups failed
        logger.warning("slack-workspace: follow-up check failed, letting message through: %s", exc)
        return None
    if skip:
        return {"action": "skip", "reason": "follow-up in an exchange addressed to someone else"}
    return None


_activity_cache = ActivityCache()


def _session_value(name: str) -> str:
    try:
        from gateway.session_context import get_session_env
    except ImportError:
        return ""
    return get_session_env(name, "").strip()


def _activity_digest(channel_id: str, current_thread: str, message_ts: str) -> str:
    try:
        hours = float(_setting("SLACK_ACTIVITY_HOURS") or 24)
        max_messages = int(_setting("SLACK_ACTIVITY_MAX_MESSAGES") or 60)
    except ValueError:
        hours, max_messages = 24.0, 60
    if hours <= 0 or max_messages <= 0:
        return ""
    workspace = _get_workspace()
    messages = _activity_cache.get(workspace._call, channel_id, hours, time.time())
    if not messages:
        return ""
    directory = workspace._user_directory()
    channel = workspace.resolve_channel(channel_id)
    return format_digest(
        messages, channel.name, workspace._own_user_id(),
        lambda uid: workspace._user(uid, directory)["name"], default_tz(), hours,
        current_thread=current_thread, exclude_ts=message_ts, max_messages=max_messages,
    )


def _limited_turn(platform: str = "") -> bool:
    return policy.is_limited(
        platform or _session_value("HERMES_SESSION_PLATFORM"),
        _session_value("HERMES_SESSION_USER_ID"), _session_value("HERMES_SESSION_CHAT_ID"),
        _session_value("HERMES_SESSION_CHAT_TYPE"))


def _pre_llm_call(platform=None, **_kwargs):
    """Every Slack turn: the tool-limit hint (when limited) and, in channels, a digest of recent
    activity across the channel's threads. Runs synchronously on the agent's worker thread
    (``invoke_hook``), not the event loop."""
    value = str(getattr(platform, "value", platform) or _session_value("HERMES_SESSION_PLATFORM") or "")
    if value.lower() != "slack":
        return None
    parts = [policy.tools_hint()] if _limited_turn(value) else []
    channel_id = _session_value("HERMES_SESSION_CHAT_ID")
    if channel_id and channel_id[0] in "CG":  # DMs: nothing to catch up on
        try:
            digest = _activity_digest(channel_id, _session_value("HERMES_SESSION_THREAD_ID"),
                                      _session_value("HERMES_SESSION_MESSAGE_ID"))
            if digest:
                parts.append(digest)
        except Exception as exc:  # noqa: BLE001 - a Slack hiccup must never block a reply
            logger.warning("slack-workspace: channel activity digest failed: %s", exc)
    return {"context": "\n\n".join(parts)} if parts else None


def _pre_tool_call(tool_name: str = "", args=None, **_kwargs):
    """Veto tools outside the Slack safe set (see policy.py)."""
    if not _limited_turn():
        return None
    reason = policy.block_reason(tool_name, args if isinstance(args, dict) else {})
    if reason:
        logger.info("slack-workspace: blocked %s on Slack for %s",
                    tool_name, _session_value("HERMES_SESSION_USER_ID") or "unknown")
        return {"action": "block", "message": reason}
    return None


def _cool_tools_command(_raw_args: str = "") -> str:
    return policy.cool_tools_text()


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


def slack_bot_manifest(args: dict, **_kwargs) -> str:
    args = args or {}
    try:
        package = manifest_package(
            str(args.get("app_name") or ""),
            description=str(args.get("description") or ""),
            display_name=str(args.get("display_name") or ""),
            background_color=str(args.get("background_color") or "#2c2d30"),
        )
    except ManifestError as exc:
        return json.dumps({"error": "invalid_manifest_input", "hint": str(exc)})
    return json.dumps(package, ensure_ascii=False)


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
    "slack_bot_manifest": (
        slack_bot_manifest,
        "Generate a Slack app manifest for an EXTERNAL bot (another person's agent) so it can "
        "communicate like Shack: read and post in channels it's invited to, DMs, files, member "
        "lists, mentions. It can never add or remove people, join or manage channels, post where "
        "it isn't a member, impersonate anyone, or use a user token. Returns the manifest JSON, "
        "what is and isn't granted, and setup steps for the bot's author.",
        {
            "app_name": {"type": "string", "description": "The bot's app name (max 35 characters)."},
            "description": {"type": "string", "description": "Short description (max 140 characters)."},
            "display_name": {"type": "string", "description": "Bot handle: lowercase letters, digits, . _ - "
                             "(default: derived from app_name)."},
            "background_color": {"type": "string", "description": "App color like #2c2d30."},
        },
        ["app_name"],
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
            check_fn=(lambda: True) if name == "slack_bot_manifest" else _available,
            description=description,
            emoji="\U0001f465",  # busts in silhouette
        )
    ctx.register_hook("pre_gateway_dispatch", _pre_gateway_dispatch)
    ctx.register_hook("pre_llm_call", _pre_llm_call)
    ctx.register_hook("pre_tool_call", _pre_tool_call)
    # Slack's /cool_tools arrives with an underscore; register both spellings so "!cool_tools"
    # and "!cool-tools" (which work in threads, where Slack rejects slash commands) resolve too.
    for name in ("cool-tools", "cool_tools"):
        ctx.register_command(name, _cool_tools_command,
                             description="Show what Shack can do for you on Slack")
    ctx.register_skill(
        "slack-workspace", _SKILL_MD,
        "Answer who is in a Slack channel and which channels Shack can see.",
    )
    ctx.register_skill(
        "slack-bot-manifest", _SKILLS_DIR / "slack-bot-manifest" / "SKILL.md",
        "Give the author of another bot a safe Slack app manifest and the channel etiquette Shack follows.",
    )
