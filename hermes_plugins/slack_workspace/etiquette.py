"""Channel etiquette: a message that opens by tagging someone is addressed to that person.

Hermes's ``SLACK_IGNORE_OTHER_USER_MENTIONS`` already drops the tagged message itself. This module
also covers what follows it: the sender's untagged follow-ups ("…and one more thing") and the
back-and-forth between the people in that exchange. Without it, a follow-up in a thread Shack is in,
or in a free-response channel, reads as addressed to Shack.
"""

from __future__ import annotations

import re

_LEADING_TAGS_RE = re.compile(r"\s*((?:<@[UW][A-Z0-9]+(?:\|[^>]*)?>[\s,:]*)+)")
_TAG_RE = re.compile(r"<@([UW][A-Z0-9]+)(?:\|[^>]*)?>")


def leading_tags(text: str) -> list[str]:
    """User IDs tagged at the very start of ``text`` (``<@A> <@B>, can you…`` → ``[A, B]``)."""
    match = _LEADING_TAGS_RE.match(text or "")
    return list(dict.fromkeys(_TAG_RE.findall(match.group(1)))) if match else []


def tagged_users(text: str) -> list[str]:
    return _TAG_RE.findall(text or "")


def _author(message: dict) -> str:
    return message.get("user") or message.get("bot_id") or ""


def continues_addressed_exchange(
    current: dict, earlier: list[dict], own_id: str, window_seconds: float,
) -> bool:
    """True when ``current`` belongs to a person-to-person exchange that Shack should stay out of.

    ``earlier`` holds the messages before ``current`` in the same place (the thread, or the
    channel's top level), newest first. Walking back within ``window_seconds``, the nearest
    message that opens by tagging someone starts an exchange between its author and the people
    tagged. ``current`` belongs to it when its author is one of them and everyone who spoke since is
    too. Anything from Shack or tagging Shack ends the walk: the conversation includes Shack again.
    """
    author = _author(current)
    if not author or (own_id and own_id in tagged_users(current.get("text") or "")):
        return False
    if [u for u in leading_tags(current.get("text") or "") if u not in (own_id, author)]:
        return True  # addressed itself (normally dropped before it gets here)
    now = float(current.get("ts") or 0)
    spoke_since: set[str] = set()
    for message in earlier:
        if now - float(message.get("ts") or 0) > window_seconds:
            return False
        speaker = _author(message)
        text = message.get("text") or ""
        if not speaker or speaker == own_id or (own_id and own_id in tagged_users(text)):
            return False
        addressed = [u for u in leading_tags(text) if u not in (own_id, speaker)]
        if addressed:
            participants = {speaker, *addressed}
            return author in participants and spoke_since <= participants
        spoke_since.add(speaker)
    return False
