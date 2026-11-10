"""Which tools Shack may use on Slack.

Everyone on Slack (people and bots, in channels and DMs) gets the same safe set: talking in Slack,
reading the web, viewing images, skills, and files under the shared workspace. The only exception
is a DM from someone listed in ``SLACK_FULL_ACCESS_USERS`` (the owner), which keeps every tool.
Anything not on the list, including tools added later, is blocked. Cron jobs, the CLI and other
platforms are unaffected.
"""

from __future__ import annotations

import os
import re

# Safe tools, grouped with a plain description for /cool_tools and the per-turn hint.
SAFE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("See who's in a channel and which channels I'm in", ("slack_channel_members", "slack_list_channels")),
    ("Ask people questions with real @tags, and collect their answers and 👍/✅ reactions",
     ("slack_post_message", "slack_get_replies")),
    ("Make a safe Slack app manifest for your own bot", ("slack_bot_manifest",)),
    ("Search the web and read web pages", ("web_search", "web_extract")),
    ("Look at images you share", ("vision_analyze",)),
    ("Read and update shared docs like the retreat PLAN.md", ("read_file", "write_file", "patch", "search_files")),
    ("Use my skills (how-tos I follow)", ("skills_list", "skill_view")),
    ("Keep a to-do list for a task, and ask you clarifying questions", ("todo_list", "clarify")),
)
SAFE_TOOLS: frozenset[str] = frozenset(t for _desc, tools in SAFE_GROUPS for t in tools)
FILE_TOOLS = frozenset({"read_file", "write_file", "patch", "search_files"})
DEFAULT_FILE_ROOTS = ("/opt/data/workspace",)

NOT_AVAILABLE = (
    "Run terminal commands or code",
    "Drive a browser, use saved logins or the password vault, or control a computer",
    "Schedule jobs, start sub-agents, or manage connections and processes",
    "Change my memory or skills",
    "Search my past conversations (they may include private DMs)",
    "Generate images or audio",
    "Read or write files outside the shared workspace",
)


def _csv(name: str) -> list[str]:
    try:
        from agent.secret_scope import get_secret

        raw = get_secret(name) or ""
    except ImportError:  # outside Hermes (tests)
        raw = os.environ.get(name, "")
    return [part.strip() for part in raw.split(",") if part.strip()]


def limits_enabled() -> bool:
    return (_csv("SLACK_TOOL_LIMITS") or ["on"])[0].lower() not in {"off", "false", "0", "no"}


def allowed_tools() -> frozenset[str]:
    return frozenset(_csv("SLACK_SAFE_TOOLS")) or SAFE_TOOLS


def file_roots() -> tuple[str, ...]:
    return tuple(os.path.realpath(r) for r in (_csv("SLACK_FILE_ROOTS") or DEFAULT_FILE_ROOTS))


def has_full_access(user_id: str, chat_id: str, chat_type: str = "") -> bool:
    """Only a true 1:1 DM (ID ``D…``). Hermes labels group DMs ``chat_type="dm"`` too, but other
    people are in those, so they get the same limits as channels."""
    del chat_type  # deliberately ignored: it can't tell a group DM from a 1:1 DM
    return bool(user_id) and chat_id.startswith("D") and user_id in _csv("SLACK_FULL_ACCESS_USERS")


def is_limited(platform: str, user_id: str, chat_id: str, chat_type: str = "") -> bool:
    return (platform.lower() == "slack" and limits_enabled()
            and not has_full_access(user_id, chat_id, chat_type))


def _path_allowed(path: str, roots: tuple[str, ...]) -> bool:
    if not path or not os.path.isabs(path):
        return False
    real = os.path.realpath(path)
    return any(real == root or real.startswith(root + os.sep) for root in roots)


def block_reason(tool_name: str, args: dict | None) -> str | None:
    """Why ``tool_name`` is blocked in a limited Slack turn, or None when it's allowed."""
    if tool_name not in allowed_tools():
        return (f"`{tool_name}` isn't available on Slack. Here Shack only uses its safe tools "
                "(type /cool_tools to see them). Tell the person you can't do that from Slack.")
    if tool_name in FILE_TOOLS:
        roots = file_roots()
        path = str((args or {}).get("path") or "")
        if not _path_allowed(path, roots):
            return (f"On Slack, files are limited to {', '.join(roots)}. Use an absolute path inside "
                    "it, or tell the person that file isn't available from Slack.")
    return None


def tools_hint() -> str:
    """One line for each limited turn so Shack doesn't try blocked tools."""
    tools = ", ".join(sorted(allowed_tools()))
    return (f"[On Slack you can only use these tools: {tools}. Files only under "
            f"{', '.join(file_roots())}. Everything else is blocked here; if someone asks for it, "
            "say it isn't available from Slack. /cool_tools shows people what you can do.]")


# Whole-message asks answered with the /cool-tools list (after the @Shack mention is stripped).
_TOOLS_REQUESTS = frozenset({
    "help", "cool-tools", "cool_tools", "cool tools", "tools", "what can you do",
    "what can you do for me", "what are your tools", "what tools do you have",
})


def is_tools_request(text: str) -> bool:
    """True when the whole message is a request for the tool list, e.g. "@Shack help". Hermes has
    already removed Shack's own <@ID> mention; anything tagging someone else never matches."""
    words = (text or "").strip().lower()
    words = re.sub(r"^@shack[\s,:]*", "", words)
    words = " ".join(words.strip(" \t\n.!?").split())
    return words in _TOOLS_REQUESTS


def cool_tools_text() -> str:
    allowed = allowed_tools()
    lines = ["*What Shack can do for you on Slack* :hammer_and_wrench:"]
    shown: set[str] = set()
    for desc, tools in SAFE_GROUPS:
        if any(t in allowed for t in tools):
            lines.append(f"• {desc}")
            shown.update(tools)
    extra = sorted(allowed - shown)
    if extra:
        lines.append(f"• Also: {', '.join(extra)}")
    lines += ["", "*Not available on Slack* (to keep everyone safe):"]
    lines += [f"• {item}" for item in NOT_AVAILABLE]
    lines += [
        "",
        "*How to ask:* mention @Shack with what you need. In channels I stay out of messages "
        "that start by tagging someone else. See this list again with `@Shack help`.",
        "*Bots and agents:* @mention Shack the same way. You get the same tools, no more.",
        "*Answer quickly:* react :+1: or :white_check_mark: for yes, :x: for no.",
    ]
    return "\n".join(lines)
