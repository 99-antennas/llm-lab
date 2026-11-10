"""Turn the agent's ``@Name`` text into real Slack ``<@UID>`` mentions.

The Hermes Slack adapter rewrites inbound ``<@UID>`` to ``@DisplayName`` before the model sees
it, so the model never learns user IDs and replies with plain-text ``@Name``, which Slack shows
as text and never notifies. This module keeps a workspace directory (``users.list``) and maps
those names back to ``<@UID>`` in the final reply.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api/"
# Broadcast keywords the adapter deliberately refuses to ping; never turn them into user mentions.
_RESERVED = {"here", "channel", "everyone"}
# Code, existing Slack entities (<@U..>, <#C..>, <url|label>), and bare URLs are left untouched.
_PROTECTED_RE = re.compile(r"```[\s\S]*?```|`[^`\n]+`|<[^<>\n]+>|https?://[^\s<>]+")
# An @ that starts a mention: not part of an email, handle path, or "@@".
_AT_RE = re.compile(r"(?<![\w@/.\-])@(?=\w)")
_TOKEN_RE = re.compile(r"[^\s]+")
_TRAILING_PUNCT = ".,:;!?)]}\"'’”"
_MAX_NAME_WORDS = 4


def _normalize(name: str) -> str:
    return " ".join(name.casefold().split())


@dataclass(frozen=True)
class SlackMember:
    user_id: str
    handle: str
    display_name: str
    real_name: str
    is_bot: bool

    @property
    def label(self) -> str:
        return self.display_name or self.real_name or self.handle or self.user_id


class MemberIndex:
    """Name → user-ID lookup. Full names/handles beat first names; ambiguous names never match."""

    def __init__(self, members: Iterable[SlackMember]):
        self.members: list[SlackMember] = list(members)
        self._strong: dict[str, set[str]] = {}
        self._weak: dict[str, set[str]] = {}
        for member in self.members:
            for name in (member.display_name, member.real_name, member.handle):
                key = _normalize(name)
                if key:
                    self._strong.setdefault(key, set()).add(member.user_id)
            for name in (member.display_name, member.real_name):
                first = _normalize(name).split(" ", 1)[0] if name.strip() else ""
                if first:
                    self._weak.setdefault(first, set()).add(member.user_id)

    def lookup(self, name: str) -> str | None:
        key = _normalize(name)
        if not key or key in _RESERVED:
            return None
        strong = self._strong.get(key)
        if strong:
            return next(iter(strong)) if len(strong) == 1 else None
        weak = self._weak.get(key)
        return next(iter(weak)) if weak and len(weak) == 1 else None


def _name_variants(candidate: str) -> list[str]:
    """Candidate spellings, longest first: ``Ray.`` → ``Ray``; ``Ray's`` → ``Ray``."""
    variants = [candidate]
    stripped = candidate.rstrip(_TRAILING_PUNCT)
    for suffix in ("'s", "’s"):
        if stripped.endswith(suffix):
            variants.append(stripped[: -len(suffix)])
    variants.append(stripped)
    seen: list[str] = []
    for v in variants:
        if v and v not in seen:
            seen.append(v)
    return seen


def _resolve_at(segment: str, start: int, index: MemberIndex) -> tuple[int, str] | None:
    """Try the longest name (up to 4 words, same line) after the ``@`` at ``start``.
    Returns ``(end, user_id)`` where ``end`` is the index just past the matched name."""
    line_end = segment.find("\n", start)
    window = segment[start + 1 : line_end if line_end != -1 else len(segment)]
    tokens = list(_TOKEN_RE.finditer(window))[:_MAX_NAME_WORDS]
    for count in range(len(tokens), 0, -1):
        candidate = window[: tokens[count - 1].end()]
        for variant in _name_variants(candidate):
            user_id = index.lookup(variant)
            if user_id:
                return start + 1 + len(variant), user_id
    return None


def _convert_segment(segment: str, index: MemberIndex) -> str:
    out: list[str] = []
    pos = 0
    for match in _AT_RE.finditer(segment):
        if match.start() < pos:
            continue
        resolved = _resolve_at(segment, match.start(), index)
        if not resolved:
            continue
        end, user_id = resolved
        out.append(segment[pos : match.start()])
        out.append(f"<@{user_id}>")
        pos = end
    out.append(segment[pos:])
    return "".join(out)


def convert_mentions(text: str, index: MemberIndex) -> str:
    """Replace resolvable ``@Name`` mentions with ``<@UID>`` outside code, links, and entities."""
    if not text or "@" not in text or not index.members:
        return text
    out: list[str] = []
    pos = 0
    for match in _PROTECTED_RE.finditer(text):
        out.append(_convert_segment(text[pos : match.start()], index))
        out.append(match.group(0))
        pos = match.end()
    out.append(_convert_segment(text[pos:], index))
    return "".join(out)


def roster_prompt(index: MemberIndex, max_members: int = 150) -> str:
    """Per-turn hint telling the agent how to tag people and who can be tagged."""
    if not index.members:
        return ""
    members = sorted(index.members, key=lambda m: m.label.casefold())[:max_members]
    entries = []
    for member in members:
        extra = [n for n in (member.real_name,) if n and n != member.label]
        entry = member.label + (f" ({', '.join(extra)})" if extra else "")
        entries.append(entry + (" [bot]" if member.is_bot else ""))
    return (
        "[Slack mentions] To notify someone on Slack, write @ followed by their name exactly as "
        "listed below (e.g. @"
        + members[0].label
        + "); it is converted into a real Slack "
        "mention automatically. Do not use #name, and do not call the Slack API to look up IDs. "
        "Workspace members (everyone in Slack, not this channel; use slack_channel_members for "
        "channel membership): " + "; ".join(entries) + "."
    )


def _member_from_payload(user: dict) -> SlackMember | None:
    if not isinstance(user, dict) or user.get("deleted") or not user.get("id"):
        return None
    if user.get("id") == "USLACKBOT":
        return None
    profile = user.get("profile") or {}
    return SlackMember(
        user_id=user["id"],
        handle=user.get("name") or "",
        display_name=(profile.get("display_name") or "").strip(),
        real_name=(profile.get("real_name") or user.get("real_name") or "").strip(),
        is_bot=bool(user.get("is_bot") or user.get("is_workflow_bot")),
    )


def _slack_call(
    token: str, method: str, params: dict | None = None, timeout: float = 10.0
) -> dict:
    url = SLACK_API + method
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("ok"):
        raise RuntimeError(
            f"Slack {method} failed: {payload.get('error', 'unknown_error')}"
        )
    return payload


def fetch_members(
    token: str, call: Callable[..., dict] = _slack_call
) -> list[SlackMember]:
    """All active members via paginated ``users.list``, minus the bot's own user."""
    own_id = call(token, "auth.test").get("user_id", "")
    members: list[SlackMember] = []
    cursor = ""
    while True:
        params = {"limit": 200}
        if cursor:
            params["cursor"] = cursor
        payload = call(token, "users.list", params)
        for user in payload.get("members", []):
            member = _member_from_payload(user)
            if member and member.user_id != own_id:
                members.append(member)
        cursor = (payload.get("response_metadata") or {}).get("next_cursor", "")
        if not cursor:
            return members


class MemberDirectory:
    """TTL-cached :class:`MemberIndex`. The first load blocks; later refreshes run in the
    background and serve the previous index meanwhile. Failures keep the last good index."""

    def __init__(
        self,
        token_fn: Callable[[], str],
        ttl_seconds: float = 900.0,
        fetch: Callable[[str], list[SlackMember]] = fetch_members,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._token_fn = token_fn
        self._ttl = ttl_seconds
        self._fetch = fetch
        self._clock = clock
        self._index = MemberIndex([])
        self._loaded_at: float | None = None
        self._lock = threading.Lock()
        self._refreshing = False

    def _refresh(self) -> None:
        try:
            token = self._token_fn()
            if not token:
                logger.warning(
                    "slack-mentions: SLACK_BOT_TOKEN is not set; mentions disabled"
                )
                return
            index = MemberIndex(self._fetch(token))
            with self._lock:
                self._index = index
            logger.info("slack-mentions: loaded %d Slack members", len(index.members))
        except Exception as exc:  # noqa: BLE001 - a Slack outage must never break replies
            logger.warning("slack-mentions: member directory refresh failed: %s", exc)
        finally:
            with self._lock:
                self._loaded_at = self._clock()
                self._refreshing = False

    def get(self) -> MemberIndex:
        with self._lock:
            loaded_at, index = self._loaded_at, self._index
            stale = loaded_at is None or self._clock() - loaded_at >= self._ttl
            start = stale and not self._refreshing
            if start:
                self._refreshing = True
        if not start:
            return index
        if loaded_at is None:
            self._refresh()
        else:
            threading.Thread(
                target=self._refresh, name="slack-mentions-refresh", daemon=True
            ).start()
        with self._lock:
            return self._index
