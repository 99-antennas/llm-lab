"""Cron ``--script`` for the 7pm retreat-planning update.

Prints the data and instructions for the agent: the current PLAN.md, the last 24h of
#retreat-planning activity across the top level and every thread, and the co-hosts to tag. The
agent posts the update with ``slack_post_message``, replies in its thread tagging the co-hosts
with concrete asks, and ends with ``[SILENT]`` so cron doesn't post a duplicate.

Co-hosts come from PLAN.md's ``*Co-hosts:* Name & Name`` line, matched to channel members, so
editing the plan changes who's tagged. ``RETREAT_COHOSTS`` (names or user IDs, comma-separated)
overrides it. Channel: ``RETREAT_PLAN_CHANNEL_ID``.
"""

from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:  # repo layout (tests)
    from hermes_plugins.slack_workspace.activity import collect, default_tz, format_digest
    from hermes_plugins.slack_workspace.workspace import (
        SlackLookupError, SlackWorkspace, _MemberNames, sdk_call_factory)
    from hermes_scripts.slack_tag_reminders import _token
except ImportError:  # Hermes image: plugin in /opt/hermes/plugins, scripts side by side
    sys.path.insert(0, "/opt/hermes/plugins")
    sys.path.insert(0, str(Path(__file__).parent))
    from slack_workspace.activity import collect, default_tz, format_digest
    from slack_workspace.workspace import SlackLookupError, SlackWorkspace, _MemberNames, sdk_call_factory
    from slack_tag_reminders import _token

HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/opt/data"))
CHANNEL_ID = os.environ.get("RETREAT_PLAN_CHANNEL_ID", "C0CF5QW6YM6")
PLAN_PATH = HERMES_HOME / "workspace" / "retreat-planning" / "PLAN.md"
HOURS = 24

INSTRUCTIONS = """\
You are posting tonight's retreat-planning update to #{channel} ({channel_id}). Use only the plan
and the channel activity below. Never invent details; label anything tentative as tentative.

1. Write the update (Slack mrkdwn, about 15 lines at most):
   *Retreat planning update: {today}*
   • *Today:* what moved in the last 24h (decisions, new info, answers). If nothing happened, say so
     in one line.
   • *Where things stand:* dates, location/lodging, attendees, budget, each in a few words.
   • *Waiting on:* the open decisions and who or what each one is waiting for.
   • *Next steps:* action items with owners.
   Refer to people by name WITHOUT an @ (the update itself must not notify anyone), and never use
   @channel or @here.
2. Post it: slack_post_message(channel="{channel_id}", text=<update>). Keep the returned ts.
3. Reply in its thread, tagging the co-hosts: slack_post_message(channel="{channel_id}",
   thread_ts=<ts from step 2>, mention={cohost_ids}, text=<check-in>). The check-in asks each
   co-host, by name, for the specific things that would move the plan forward or unblock a
   decision: questions waiting on them, action items they own, choices only they can make. Give
   each one 1-3 concrete asks. If nothing specific is waiting on someone, ask whether anything is
   blocking them or whether they need anything. End by asking them to reply in this thread.
4. Don't edit PLAN.md.
5. If both posts succeeded, your final response is exactly [SILENT]. If a post failed, your final
   response says what failed and why (it is sent to the operator).
"""


_COHOSTS_LINE_RE = re.compile(r"^\W*co-?hosts?\W*:\W*(.+)$", re.IGNORECASE | re.MULTILINE)


def cohosts_from_plan(plan_text: str) -> list[str]:
    """Names on PLAN.md's co-hosts line: ``*Co-hosts:* Kas Stohr & Ray McLendon — note`` → both."""
    match = _COHOSTS_LINE_RE.search(plan_text or "")
    if not match:
        return []
    names = re.split(r"\s+[—–]\s+|\s+-\s+|\s*\(", match.group(1), maxsplit=1)[0]
    parts = re.split(r"\s*(?:&|,|\band\b|\+)\s*", names.strip(" *_"))
    return [p.strip(" *_.") for p in parts if p.strip(" *_.")]


def cohosts(plan_text: str) -> list[str]:
    override = [p.strip() for p in os.environ.get("RETREAT_COHOSTS", "").split(",") if p.strip()]
    return override or cohosts_from_plan(plan_text)


def resolve_cohosts(names: list[str], members: list[dict]) -> tuple[dict[str, str], list[str]]:
    """``({user_id: display name}, unresolved names)`` against the channel's members."""
    index = _MemberNames(members)
    by_id = {m["id"]: m["name"] for m in members}
    resolved, unresolved = {}, []
    for name in names:
        uid = index.lookup(name)
        if uid:
            resolved[uid] = by_id.get(uid, name)
        else:
            unresolved.append(name)
    return resolved, unresolved


def build_output(today: str, channel: str, channel_id: str, cohost_names: dict[str, str],
                 plan_text: str, digest: str) -> str:
    ids = list(cohost_names)
    who = ", ".join(f"{name} ({uid})" for uid, name in cohost_names.items()) or "none configured"
    parts = [
        INSTRUCTIONS.format(channel=channel, channel_id=channel_id, today=today, cohost_ids=ids),
        f"Co-hosts to tag in step 3: {who}",
        "",
        "=== PLAN.md (shared retreat plan) ===",
        plan_text.strip() or "(PLAN.md is empty or missing)",
        "",
        f"=== #{channel} activity, last {HOURS}h, all threads ===",
        digest.strip() or f"No messages in the last {HOURS} hours.",
    ]
    return "\n".join(parts)


def main() -> int:
    plan_text = PLAN_PATH.read_text() if PLAN_PATH.exists() else ""
    names = cohosts(plan_text)
    if not names:
        print("retreat_daily_update: no co-hosts (add a '*Co-hosts:* A & B' line to PLAN.md "
              "or set RETREAT_COHOSTS)", file=sys.stderr)
        return 1
    token = _token()
    if not token:
        print("retreat_daily_update: SLACK_BOT_TOKEN not found", file=sys.stderr)
        return 1
    workspace = SlackWorkspace(sdk_call_factory(token))
    channel = workspace.resolve_channel(CHANNEL_ID)
    directory = workspace._user_directory()

    def name(uid: str) -> str:
        return workspace._user(uid, directory)["name"]

    people, _bots = workspace._members(channel)
    resolved, unresolved = resolve_cohosts(names, people)
    if unresolved:
        print(f"retreat_daily_update: co-hosts not found in #{channel.name}: {', '.join(unresolved)}",
              file=sys.stderr)
        return 1

    tz = default_tz()
    now = time.time()
    messages = collect(workspace._call, channel.id, now - HOURS * 3600)
    digest = format_digest(messages, channel.name, workspace._own_user_id(), name, tz, HOURS,
                           max_messages=150, max_chars=20000)
    # The digest header tells a live turn not to reply; this run only summarizes.
    digest = "\n".join(digest.splitlines()[1:]) if digest else ""
    today = datetime.fromtimestamp(now, tz).strftime("%A, %B %-d")
    print(build_output(today, channel.name, channel.id, resolved, plan_text, digest))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SlackLookupError as exc:
        print(f"retreat_daily_update: Slack error {exc.to_dict()}", file=sys.stderr)
        sys.exit(1)
