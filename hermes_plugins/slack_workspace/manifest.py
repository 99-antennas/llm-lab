"""Slack app manifests for external bots that should communicate like Shack, minus anything risky.

Granted: read and post in channels the bot is *invited* to, DMs and group DMs, files, member
lists and profiles, mentions. Never granted: anything that adds or removes people, joins or manages
channels, posts where the bot isn't a member, impersonates people, edits workspace state, or
uses a *user* token (which would act as a human). ``build_manifest`` refuses to emit a forbidden
scope even if the lists below are edited by mistake.
"""

from __future__ import annotations

import json
import re

# Shack's communication scopes (see slack-manifest.json) minus `commands` (slash commands are
# Hermes-specific and their names would collide with Shack's).
EXTERNAL_BOT_SCOPES: tuple[str, ...] = (
    "app_mentions:read",   # see @mentions of the bot
    "assistant:write",     # Slack's assistant thread UI
    "channels:history",    # read messages in public channels it was invited to
    "channels:read",       # list public channels and their members
    "chat:write",          # post (only where it's a member) and edit/delete its OWN messages
    "files:read",          # read files shared with it
    "files:write",         # upload files (can only delete files it uploaded)
    "groups:history",      # read private channels it was invited to
    "groups:read",         # list private channels it's in and their members
    "im:history",          # read its DMs
    "im:read",             # list its DMs
    "im:write",            # open a DM with someone
    "mpim:read",           # list group DMs it's in
    "users:read",          # names, titles, timezones (no emails)
)

EXTERNAL_BOT_EVENTS: tuple[str, ...] = (
    "app_mention",
    "assistant_thread_context_changed",
    "assistant_thread_started",
    "message.channels",
    "message.groups",
    "message.im",
)

# What each blocked scope would have allowed. Shown to the bot's author.
FORBIDDEN_SCOPES: dict[str, str] = {
    "channels:manage": "create, archive, rename public channels; remove members",
    "channels:join": "join public channels on its own (it must be invited)",
    "channels:write.invites": "add people to public channels",
    "channels:write.topic": "change channel topics",
    "groups:write": "create, archive, rename private channels; remove members",
    "groups:write.invites": "add people to private channels",
    "groups:write.topic": "change private channel topics",
    "im:write.topic": "change DM topics",
    "mpim:write": "start group DMs",
    "mpim:write.invites": "add people to group DMs",
    "mpim:write.topic": "change group DM topics",
    "chat:write.public": "post in channels it isn't a member of",
    "chat:write.customize": "post under another name or avatar (impersonation)",
    "users:read.email": "read people's email addresses",
    "users:write": "change presence",
    "users.profile:write": "edit profiles",
    "usergroups:write": "create or change user groups",
    "pins:write": "pin or unpin messages",
    "bookmarks:write": "add or remove channel bookmarks",
    "reminders:write": "create reminders for people",
    "calls:write": "start calls",
    "conversations.connect:manage": "manage Slack Connect channels",
    "conversations.connect:write": "invite other workspaces to channels",
    "remote_files:write": "add or remove remote files",
    "dnd:write": "change people's do-not-disturb",
}
# Plain-language summary sent to the bot's author. Kept next to the scope lists so they change
# together; tests check every granted scope is covered.
CAN_DO: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Read and post messages in channels it has been invited to (public and private)",
     ("channels:history", "groups:history", "chat:write")),
    ("Read its DMs, reply to them, and start a DM with someone", ("im:history", "im:read", "im:write")),
    ("See which channels and group DMs it's in, and who the members are",
     ("channels:read", "groups:read", "mpim:read")),
    ("See people's names, titles and timezones (not email addresses)", ("users:read",)),
    ("Notice when someone @mentions it", ("app_mentions:read",)),
    ("Read files shared with it and upload files", ("files:read", "files:write")),
    ("Edit or delete only its own messages and files", ("chat:write", "files:write")),
    ("Use Slack's assistant threads", ("assistant:write",)),
)
CANNOT_DO: tuple[str, ...] = (
    "Add or remove people from channels or group DMs",
    "Create, archive or rename channels, or change topics",
    "Join channels on its own (someone has to /invite it)",
    "Post in channels it isn't a member of",
    "Post under someone else's name or avatar",
    "Read people's email addresses",
    "Change profiles, presence, user groups, pins, bookmarks, reminders or do-not-disturb",
    "Start calls, invite other workspaces (Slack Connect), or do anything admin-level",
    "Act as a person: it gets a bot token only, never a user token",
)

# Any scope with these prefixes is admin-level.
_FORBIDDEN_PREFIXES = ("admin",)

_NAME_MAX, _DISPLAY_MAX, _DESC_MAX = 35, 80, 140
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_DISPLAY_NAME_RE = re.compile(r"^[a-z0-9._-]+$")


class ManifestError(ValueError):
    pass


def _is_forbidden(scope: str) -> bool:
    return scope in FORBIDDEN_SCOPES or scope.startswith(_FORBIDDEN_PREFIXES)


def _display_name(app_name: str) -> str:
    """Slack bot display names: lowercase letters, digits, ``.``, ``_``, ``-``."""
    slug = re.sub(r"[^a-z0-9._-]+", "-", app_name.lower()).strip("-.")
    return slug or "bot"


def build_manifest(
    app_name: str,
    description: str = "",
    display_name: str = "",
    background_color: str = "#2c2d30",
) -> dict:
    app_name = (app_name or "").strip()
    if not app_name:
        raise ManifestError("app_name is required")
    if len(app_name) > _NAME_MAX:
        raise ManifestError(f"app_name must be at most {_NAME_MAX} characters")
    description = (description or f"{app_name} on Slack").strip()
    if len(description) > _DESC_MAX:
        raise ManifestError(f"description must be at most {_DESC_MAX} characters")
    display_name = (display_name or _display_name(app_name)).strip()
    if len(display_name) > _DISPLAY_MAX or not _DISPLAY_NAME_RE.match(display_name):
        raise ManifestError("display_name must be lowercase letters, digits, '.', '_' or '-' "
                            f"(at most {_DISPLAY_MAX} characters)")
    if not _COLOR_RE.match(background_color or ""):
        raise ManifestError("background_color must look like #1a2b3c")

    scopes = sorted(set(EXTERNAL_BOT_SCOPES))
    blocked = [s for s in scopes if _is_forbidden(s)]
    if blocked:  # guards against someone editing EXTERNAL_BOT_SCOPES carelessly
        raise ManifestError(f"refusing to grant forbidden scopes: {', '.join(blocked)}")

    return {
        "_metadata": {"major_version": 1, "minor_version": 1},
        "display_information": {
            "name": app_name,
            "description": description,
            "background_color": background_color.lower(),
        },
        "features": {
            "app_home": {
                "home_tab_enabled": False,
                "messages_tab_enabled": True,
                "messages_tab_read_only_enabled": False,
            },
            "bot_user": {"display_name": display_name, "always_online": True},
            "assistant_view": {"assistant_description": f"Chat with {app_name} in threads and DMs."},
        },
        # Bot scopes only: a user token would let the app act as the person who installed it.
        "oauth_config": {"scopes": {"bot": scopes}},
        "settings": {
            "event_subscriptions": {"bot_events": list(EXTERNAL_BOT_EVENTS)},
            "interactivity": {"is_enabled": True},
            "org_deploy_enabled": False,
            "socket_mode_enabled": True,
            "token_rotation_enabled": False,
        },
    }


def manifest_package(app_name: str, description: str = "", display_name: str = "",
                     background_color: str = "#2c2d30") -> dict:
    """The manifest plus everything the bot's author needs to know."""
    manifest = build_manifest(app_name, description, display_name, background_color)
    handle = manifest["features"]["bot_user"]["display_name"]
    summary = "\n".join(
        [f"*What {manifest['display_information']['name']} can do*"]
        + [f"• {line}" for line, _scopes in CAN_DO]
        + ["", "*What it can't do*"]
        + [f"• {line}" for line in CANNOT_DO]
    )
    return {
        "manifest": manifest,
        "manifest_json": json.dumps(manifest, indent=2),
        "permissions_summary": summary,
        "granted": list(manifest["oauth_config"]["scopes"]["bot"]),
        "not_granted": [f"{scope}: {why}" for scope, why in FORBIDDEN_SCOPES.items()],
        "setup_steps": [
            "Go to https://api.slack.com/apps → Create New App → From a manifest, pick this workspace.",
            "Paste the JSON manifest, review, and create the app.",
            "Basic Information → App-Level Tokens → generate a token with connections:write "
            "(Socket Mode), then Install to Workspace to get the bot token (xoxb-…).",
            f"A channel member invites the bot to each channel it should work in: /invite @{handle}",
            "Don't add any scope listed under not_granted without asking the channel's owners first.",
        ],
    }
