"""Cron ``--no-agent`` script: remind people who were tagged at the start of a message and never
answered.

Channel convention: a message that *opens* by tagging someone (``@Ray can you book the cabin?``)
is addressed to that person, so others (Shack included, via SLACK_IGNORE_OTHER_USER_MENTIONS)
stay out of it. If the person tagged hasn't responded after ``SLACK_REMINDER_AFTER_HOURS`` (24),
this posts one reminder in the message's thread, tagging them.

Counts as a response: a later reply by them in that thread, a later top-level message by them in
the channel, or a 👍/✅ (or 👎/❌) reaction by them on the message; 👀 or 😂 don't count. Each tag gets at most one reminder:
an earlier Shack message in the thread that tags them counts as the reminder. Messages Shack
posted itself are skipped (``slack_get_replies`` tracks those). Messages older than
``SLACK_REMINDER_LOOKBACK_DAYS`` (3) are never reminded about.

Channels: ``SLACK_REMINDER_CHANNELS``, else ``SLACK_POST_CHANNELS`` (names or IDs, comma-separated).
Prints a line per reminder sent (nothing when there's nothing to do). ``--dry-run`` only prints.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

try:  # repo layout (tests)
    from hermes_plugins.slack_workspace.etiquette import leading_tags, tagged_users
    from hermes_plugins.slack_workspace.reactions import answers as reaction_answers
    from hermes_plugins.slack_workspace.workspace import SlackLookupError, SlackWorkspace, sdk_call_factory
except ImportError:  # Hermes image: the plugin lives in /opt/hermes/plugins/slack_workspace
    sys.path.insert(0, "/opt/hermes/plugins")
    from slack_workspace.etiquette import leading_tags, tagged_users
    from slack_workspace.reactions import answers as reaction_answers
    from slack_workspace.workspace import SlackLookupError, SlackWorkspace, sdk_call_factory

HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/opt/data"))
S6_ENV_DIR = Path("/run/s6/container_environment")
# Ordinary messages and thread replies broadcast to the channel; joins, edits, bot posts are skipped.
_HUMAN_SUBTYPES = {None, "", "thread_broadcast", "file_share"}


@dataclass(frozen=True)
class Reminder:
    channel_id: str
    thread_ts: str
    message_ts: str
    author_id: str
    user_ids: tuple[str, ...]


def _ts(message: dict) -> float:
    return float(message.get("ts") or 0)


def find_overdue(
    channel_id: str,
    top_level: list[dict],
    threads: dict[str, list[dict]],
    own_id: str,
    now: float,
    after_seconds: float,
    lookback_seconds: float,
    is_person: Callable[[str], bool],
) -> list[Reminder]:
    """Reminders due in one channel. ``threads`` maps a root ts to that thread's messages
    (root first); ``top_level`` is the channel history."""
    candidates = list(top_level)
    for root, messages in threads.items():
        candidates.extend(m for m in messages if m.get("ts") != root)
    reminders: list[Reminder] = []
    for msg in candidates:
        author = msg.get("user") or ""
        if (not author or author == own_id or msg.get("bot_id")
                or msg.get("subtype") not in _HUMAN_SUBTYPES):
            continue
        age = now - _ts(msg)
        if age < after_seconds or age > lookback_seconds:
            continue
        tagged = [u for u in leading_tags(msg.get("text") or "")
                  if u not in (own_id, author) and is_person(u)]
        if not tagged:
            continue
        root = msg.get("thread_ts") or msg["ts"]
        thread = threads.get(root, [])
        later_thread = [m for m in thread if _ts(m) > _ts(msg)]
        later_top = [m for m in top_level if _ts(m) > _ts(msg)]
        reacted = set(reaction_answers(msg))  # 👍/✅/👎/❌ answer; 👀 or 😂 don't
        due = []
        for user in tagged:
            responded = (user in reacted
                         or any(m.get("user") == user for m in later_thread + later_top))
            reminded = any(m.get("user") == own_id and user in tagged_users(m.get("text") or "")
                           for m in later_thread)
            if not responded and not reminded:
                due.append(user)
        if due:
            reminders.append(Reminder(channel_id, root, msg["ts"], author, tuple(due)))
    return reminders


def reminder_text(reminder: Reminder, permalink: str = "") -> str:
    tags = " ".join(f"<@{u}>" for u in reminder.user_ids)
    target = f"<{permalink}|this message>" if permalink else "the message above"
    return (f"{tags} friendly reminder: <@{reminder.author_id}> is waiting on your reply to "
            f"{target}. Reply here when you can :pray:")


def _token() -> str:
    token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    if token:
        return token
    # Cron scrubs secrets from a script's env. The GSM secrets init exports the token into the
    # s6 container environment; a plain HERMES_HOME/.env is the fallback for other setups.
    s6_file = S6_ENV_DIR / "SLACK_BOT_TOKEN"
    try:
        token = s6_file.read_text().strip()
    except OSError:
        token = ""
    if token:
        return token
    env_file = HERMES_HOME / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "SLACK_BOT_TOKEN":
                return value.strip().strip("'\"")
    return ""


def _channels() -> list[str]:
    raw = os.environ.get("SLACK_REMINDER_CHANNELS") or os.environ.get("SLACK_POST_CHANNELS") or ""
    return [part.strip() for part in raw.split(",") if part.strip()]


def run(call, channels: list[str], now: float, after_hours: float, lookback_days: float,
        dry_run: bool = False) -> list[str]:
    workspace = SlackWorkspace(call)
    own_id = call("auth.test").get("user_id", "")
    people: dict[str, bool] = {}

    def is_person(user_id: str) -> bool:
        if user_id not in people:
            try:
                user = call("users.info", user=user_id)["user"]
                people[user_id] = not (user.get("is_bot") or user.get("is_workflow_bot")
                                       or user.get("deleted") or user_id == "USLACKBOT")
            except SlackLookupError:
                people[user_id] = False
        return people[user_id]

    after, lookback = after_hours * 3600, lookback_days * 86400
    sent: list[str] = []
    for ref in channels:
        channel = workspace.resolve_channel(ref)
        top_level: list[dict] = []
        cursor = ""
        while True:
            params = {"channel": channel.id, "oldest": f"{now - lookback:.6f}", "limit": 200}
            if cursor:
                params["cursor"] = cursor
            page = call("conversations.history", **params)
            top_level.extend(page.get("messages") or [])
            cursor = (page.get("response_metadata") or {}).get("next_cursor", "")
            if not cursor:
                break
        threads = {m["ts"]: call("conversations.replies", channel=channel.id, ts=m["ts"],
                                 limit=200).get("messages") or []
                   for m in top_level if m.get("reply_count")}
        for reminder in find_overdue(channel.id, top_level, threads, own_id, now, after, lookback,
                                     is_person):
            try:
                permalink = call("chat.getPermalink", channel=channel.id,
                                 message_ts=reminder.message_ts).get("permalink", "")
            except SlackLookupError:
                permalink = ""
            text = reminder_text(reminder, permalink)
            if not dry_run:
                call("chat.postMessage", channel=channel.id, thread_ts=reminder.thread_ts, text=text,
                     unfurl_links=False, link_names=False)
            sent.append(f"#{channel.name}: reminded {', '.join(reminder.user_ids)} about "
                        f"{reminder.message_ts}{' (dry run)' if dry_run else ''}")
    return sent


def main(argv: list[str]) -> int:
    channels = _channels()
    if not channels:
        return 0
    token = _token()
    if not token:
        print("slack_tag_reminders: SLACK_BOT_TOKEN not found", file=sys.stderr)
        return 1
    dry_run = "--dry-run" in argv or os.environ.get("SLACK_REMINDER_DRY_RUN") == "1"
    sent = run(sdk_call_factory(token), channels, time.time(),
               after_hours=float(os.environ.get("SLACK_REMINDER_AFTER_HOURS") or 24),
               lookback_days=float(os.environ.get("SLACK_REMINDER_LOOKBACK_DAYS") or 3),
               dry_run=dry_run)
    for line in sent:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
