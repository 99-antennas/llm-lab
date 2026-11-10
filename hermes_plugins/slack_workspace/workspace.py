"""Slack Web API lookups for the agent: which channels the bot is in, and who is in a channel.

The Hermes Slack adapter only hands the agent message text, so on its own the agent cannot answer
"who's in this channel?". This module wraps ``slack_sdk`` (already in the Hermes image) behind a
small ``call(method, **params) -> dict`` seam so the logic is testable without Slack.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SlackCall = Callable[..., dict]

# Conversation IDs: C (public), G (private/legacy mpim), D (DM).
_CHANNEL_ID_RE = re.compile(r"^[CGD][A-Z0-9]{6,}$")
# Slack's own channel reference: <#C0123ABCD|name> or <#C0123ABCD>.
_CHANNEL_REF_RE = re.compile(r"^<#([CGD][A-Z0-9]{6,})(?:\|[^>]*)?>$")
_ALL_TYPES = "public_channel,private_channel,mpim"
_NO_MPIM_TYPES = "public_channel,private_channel"
MAX_MEMBERS = 500
MAX_POST_CHARS = 3500
# Slack methods that change state go out as POST.
_WRITE_METHODS = {"chat.postMessage"}

_ERROR_HINTS = {
    "not_in_channel": "Shack is not a member of that channel. Ask someone to run `/invite @Shack` there.",
    "channel_not_found": (
        "Shack can't see that channel. It is private and Shack is not in it, or the ID is wrong. "
        "Use slack_list_channels to see the channels Shack can access."
    ),
    "missing_scope": "The Slack app lacks a required OAuth scope; add it in the app config and reinstall.",
    "invalid_auth": "SLACK_BOT_TOKEN is invalid or revoked.",
    "not_authed": "SLACK_BOT_TOKEN is not set.",
    "channel_not_allowed": (
        "Shack may only post in the channels listed in SLACK_POST_CHANNELS. Ask the operator to add "
        "this channel there."
    ),
    "unknown_members": (
        "Some @names don't match anyone in the channel, so nothing was posted. Use the exact names "
        "from channel_members (or their <@ID> mention) and try again."
    ),
    "empty_message": "The message text is empty.",
    "invalid_broadcast": "broadcast must be 'channel' or 'here' (or left out).",
    "no_channel": "Pass a channel name or ID; this conversation is not a Slack channel.",
    "message_too_long": "Keep the message under 3500 characters.",
    "message_not_found": "No message with that ts in this channel. Use the ts returned by slack_post_message.",
}


class SlackLookupError(Exception):
    def __init__(self, code: str, needed: str = "", detail: dict | None = None):
        self.code = code
        self.needed = needed
        self.detail = detail or {}
        super().__init__(code)

    def to_dict(self) -> dict:
        out = {"error": self.code}
        hint = _ERROR_HINTS.get(self.code)
        if hint:
            out["hint"] = hint
        if self.needed:
            out["needed_scope"] = self.needed
        out.update(self.detail)
        return out


@dataclass(frozen=True)
class Channel:
    id: str
    name: str
    is_private: bool
    is_member: bool
    is_im: bool = False
    is_mpim: bool = False
    num_members: int | None = None
    topic: str = ""
    purpose: str = ""

    def to_dict(self) -> dict:
        out = {
            "id": self.id,
            "name": self.name,
            "kind": "dm" if self.is_im else "group_dm" if self.is_mpim else
                    "private_channel" if self.is_private else "public_channel",
            "shack_is_member": self.is_member,
        }
        if self.num_members is not None:
            out["num_members"] = self.num_members
        if self.topic:
            out["topic"] = self.topic
        if self.purpose:
            out["purpose"] = self.purpose
        return out


def _channel_from_payload(data: dict) -> Channel:
    return Channel(
        id=data["id"],
        name=data.get("name") or data.get("user") or data["id"],
        is_private=bool(data.get("is_private") or data.get("is_group")),
        is_member=bool(data.get("is_member", True)),
        is_im=bool(data.get("is_im")),
        is_mpim=bool(data.get("is_mpim")),
        num_members=data.get("num_members"),
        topic=((data.get("topic") or {}).get("value") or "").strip(),
        purpose=((data.get("purpose") or {}).get("value") or "").strip(),
    )


def _user_from_payload(user: dict) -> dict:
    profile = user.get("profile") or {}
    display = (profile.get("display_name") or "").strip()
    real = (profile.get("real_name") or user.get("real_name") or "").strip()
    out = {
        "id": user["id"],
        "name": display or real or user.get("name") or user["id"],
        "mention": f"<@{user['id']}>",
    }
    if real and real != out["name"]:
        out["real_name"] = real
    if user.get("name"):
        out["handle"] = user["name"]
    title = (profile.get("title") or "").strip()
    if title:
        out["title"] = title
    if user.get("tz"):
        out["timezone"] = user["tz"]
    if user.get("is_bot") or user.get("is_workflow_bot") or user["id"] == "USLACKBOT":
        out["is_bot"] = True
    if user.get("deleted"):
        out["deactivated"] = True
    return out


def _paginate(call: SlackCall, method: str, key: str, **params) -> list:
    items: list = []
    cursor = ""
    while True:
        page = dict(params, limit=params.get("limit", 200))
        if cursor:
            page["cursor"] = cursor
        payload = call(method, **page)
        items.extend(payload.get(key) or [])
        cursor = (payload.get("response_metadata") or {}).get("next_cursor", "")
        if not cursor:
            return items


class SlackWorkspace:
    """Cached channel/user lookups over a Slack ``call``. Users refresh every ``ttl`` seconds."""

    def __init__(
        self,
        call: SlackCall,
        ttl_seconds: float = 900.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._call = call
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._users: dict[str, dict] = {}
        self._users_loaded_at: float | None = None
        self._mpim_supported = True
        self._own_id: str | None = None

    # -- channels ---------------------------------------------------------------------------

    def _member_channels(self) -> list[Channel]:
        """Conversations the bot belongs to. Falls back without group DMs if ``mpim:read`` is missing."""
        types = _ALL_TYPES if self._mpim_supported else _NO_MPIM_TYPES
        try:
            raw = _paginate(self._call, "users.conversations", "channels",
                            types=types, exclude_archived=True)
        except SlackLookupError as exc:
            if exc.code != "missing_scope" or types == _NO_MPIM_TYPES:
                raise
            logger.info("slack-workspace: no mpim:read scope; group DMs are not listed")
            self._mpim_supported = False
            raw = _paginate(self._call, "users.conversations", "channels",
                            types=_NO_MPIM_TYPES, exclude_archived=True)
        return [_channel_from_payload(dict(c, is_member=True)) for c in raw]

    def list_channels(self, query: str = "") -> list[Channel]:
        channels = self._member_channels()
        needle = query.strip().lstrip("#").casefold()
        if needle:
            channels = [c for c in channels if needle in c.name.casefold()]
        return sorted(channels, key=lambda c: c.name.casefold())

    def resolve_channel(self, ref: str) -> Channel:
        """Accept a channel ID, ``<#ID|name>``, ``#name`` or ``name``."""
        ref = (ref or "").strip()
        match = _CHANNEL_REF_RE.match(ref)
        channel_id = match.group(1) if match else ref if _CHANNEL_ID_RE.match(ref) else ""
        if channel_id:
            payload = self._call("conversations.info", channel=channel_id, include_num_members=True)
            return _channel_from_payload(payload["channel"])
        name = ref.lstrip("#").casefold()
        if not name:
            raise SlackLookupError("channel_not_found")
        for channel in self._member_channels():
            if channel.name.casefold() == name:
                return channel
        # Public channels Shack hasn't joined are still visible with channels:read.
        for raw in _paginate(self._call, "conversations.list", "channels",
                             types="public_channel", exclude_archived=True, limit=1000):
            if (raw.get("name") or "").casefold() == name:
                return _channel_from_payload(raw)
        raise SlackLookupError("channel_not_found")

    # -- users ------------------------------------------------------------------------------

    def _user_directory(self) -> dict[str, dict]:
        with self._lock:
            fresh = self._users_loaded_at is not None and self._clock() - self._users_loaded_at < self._ttl
            if fresh:
                return self._users
        try:
            users = {u["id"]: u for u in _paginate(self._call, "users.list", "members") if u.get("id")}
        except SlackLookupError as exc:
            logger.warning("slack-workspace: users.list failed (%s); falling back to users.info", exc.code)
            users = {}
        with self._lock:
            if users:
                self._users = users
            self._users_loaded_at = self._clock()
            return self._users

    def _user(self, user_id: str, directory: dict[str, dict]) -> dict:
        user = directory.get(user_id)
        if user is None:
            try:
                user = self._call("users.info", user=user_id)["user"]
                with self._lock:
                    self._users[user_id] = user
            except SlackLookupError:
                user = {"id": user_id}
        return _user_from_payload(user)

    # -- members ----------------------------------------------------------------------------

    def _members(self, channel: Channel) -> tuple[list[dict], list[dict]]:
        """``(people, bots)`` in ``channel``; deactivated accounts are dropped from people."""
        member_ids = _paginate(self._call, "conversations.members", "members", channel=channel.id)
        directory = self._user_directory()
        members = [self._user(uid, directory) for uid in member_ids]
        bots = [m for m in members if m.get("is_bot")]
        people = [m for m in members if not m.get("is_bot") and not m.get("deactivated")]
        return people, bots

    def channel_members(self, ref: str, include_bots: bool = False) -> dict:
        channel = self.resolve_channel(ref)
        people, bots = self._members(channel)
        listed = people + (bots if include_bots else [])
        listed.sort(key=lambda m: m["name"].casefold())
        result = {
            "channel": channel.to_dict(),
            "member_count": len(people),
            "bot_count": len(bots),
            "members": listed[:MAX_MEMBERS],
        }
        if len(listed) > MAX_MEMBERS:
            result["truncated"] = True
        return result

    # -- posting and collecting replies -----------------------------------------------------

    def _own_user_id(self) -> str:
        if self._own_id is None:
            self._own_id = self._call("auth.test").get("user_id", "")
        return self._own_id

    def post_message(
        self, channel: Channel, text: str, thread_ts: str = "", mention: str | list | None = None,
        broadcast: str = "",
    ) -> dict:
        """Post ``text`` to ``channel`` with ``@Name`` turned into real ``<@UID>`` tags.

        ``mention="all"`` tags every person in the channel; a list tags those people. Nothing is
        posted if any name can't be matched to a channel member, so nobody silently misses it.
        ``broadcast="channel"``/``"here"`` adds a real ``@channel``/``@here``. That is the only
        way to broadcast: raw ``<!channel>``-style syntax in ``text`` is posted as plain text.
        """
        text = (text or "").strip()
        broadcast = (broadcast or "").strip().lower().lstrip("@")
        if not text:
            raise SlackLookupError("empty_message")
        if len(text) > MAX_POST_CHARS:
            raise SlackLookupError("message_too_long")
        if broadcast not in BROADCASTS:
            raise SlackLookupError("invalid_broadcast")
        people, bots = self._members(channel)
        index = _MemberNames(people + bots)
        tagged_text, tagged, unresolved, broadcast_used = index.tag_text(text, broadcast)

        extra: list[str] = []
        if mention == "all":
            extra = [p["id"] for p in people]
        elif isinstance(mention, list):
            for name in mention:
                uid = index.lookup(str(name))
                if uid:
                    extra.append(uid)
                else:
                    unresolved.append(str(name))
        if unresolved:
            raise SlackLookupError(
                "unknown_members", detail={
                    "unresolved": sorted(set(unresolved)),
                    "channel_members": sorted(p["name"] for p in people),
                })
        prefix = [uid for uid in dict.fromkeys(extra) if uid not in tagged and uid != self._own_user_id()]
        lead = [f"<@{uid}>" for uid in prefix]
        if broadcast and not broadcast_used:
            lead.insert(0, f"<!{broadcast}>")
        if lead:
            tagged_text = " ".join(lead) + " " + tagged_text
        tagged = list(dict.fromkeys(tagged + prefix))

        # link_names off: Slack must not turn any leftover plain "@channel" text into a broadcast.
        params = {"channel": channel.id, "text": tagged_text, "unfurl_links": False, "link_names": False}
        if thread_ts:
            params["thread_ts"] = thread_ts
        payload = self._call("chat.postMessage", **params)
        names = {m["id"]: m["name"] for m in people + bots}
        return {
            "ok": True,
            "channel": channel.to_dict(),
            "ts": payload.get("ts", ""),
            "thread_ts": thread_ts or payload.get("ts", ""),
            "tagged": [names.get(uid, uid) for uid in tagged],
            "broadcast": broadcast or None,
            "text": tagged_text,
        }

    def get_replies(self, channel: Channel, ts: str) -> dict:
        """Answers to the message at ``ts``: thread replies plus later channel messages from the
        people it tagged. ``waiting_on`` lists tagged people who haven't answered yet."""
        own_id = self._own_user_id()
        thread = _paginate(self._call, "conversations.replies", "messages", channel=channel.id, ts=ts)
        if not thread:
            raise SlackLookupError("message_not_found")
        question = thread[0]
        question_text = question.get("text") or ""
        asked = list(dict.fromkeys(_USER_TAG_RE.findall(question_text)))
        broadcast = next((b for b in BROADCASTS if b and f"<!{b}" in question_text), "")
        if broadcast:
            # A broadcast asks everyone, so track every person currently in the channel.
            people, _bots = self._members(channel)
            asked = list(dict.fromkeys(asked + [p["id"] for p in people]))
        asked = [uid for uid in asked if uid != own_id]

        responses: list[tuple[dict, str]] = [(m, "thread") for m in thread[1:]]
        later = _paginate(self._call, "conversations.history", "messages",
                          channel=channel.id, oldest=ts, limit=200)
        responses += [(m, "channel") for m in later
                      if m.get("user") in asked and m.get("ts") != ts
                      and (not m.get("thread_ts") or m.get("thread_ts") == m.get("ts"))]

        directory = self._user_directory()
        out, answered = [], set()
        for msg, where in sorted(responses, key=lambda r: float(r[0].get("ts") or 0)):
            uid = msg.get("user") or ""
            if not uid or uid == own_id or msg.get("bot_id"):
                continue
            answered.add(uid)
            out.append({"user_id": uid, "name": self._user(uid, directory)["name"],
                        "text": msg.get("text") or "", "ts": msg.get("ts"), "where": where})
        return {
            "channel": channel.to_dict(),
            "question": question_text,
            "broadcast": broadcast or None,
            "asked": [self._user(uid, directory)["name"] for uid in asked],
            "responses": out,
            "waiting_on": [self._user(uid, directory)["name"] for uid in asked if uid not in answered],
        }


BROADCASTS = ("", "channel", "here")
# Raw broadcast / user-group syntax the model might write; posted as plain text, never as a ping.
_RAW_BROADCAST_RE = re.compile(r"^<!(channel|here|everyone|subteam\^[A-Z0-9]+)(?:\|([^>]*))?>$")
_USER_TAG_RE = re.compile(r"<@([UW][A-Z0-9]+)(?:\|[^>]*)?>")
# Code and existing Slack entities (<@U..>, <#C..>, <url|label>) are never rewritten.
_PROTECTED_RE = re.compile(r"```[\s\S]*?```|`[^`\n]+`|<[^<>\n]+>|https?://[^\s<>]+")
_AT_RE = re.compile(r"(?<![\w@/.\-])@(?=\w)")
_WORD_RE = re.compile(r"[^\s]+")
_TRAILING_PUNCT = ".,:;!?)]}\"'’”"
_RESERVED = {"here", "channel", "everyone"}


class _MemberNames:
    """Channel-scoped ``@Name`` → user ID. Full names/handles beat unique first names."""

    def __init__(self, members: list[dict]):
        self._strong: dict[str, set[str]] = {}
        self._weak: dict[str, set[str]] = {}
        self._ids = {m["id"] for m in members}
        for m in members:
            names = [m.get("name", ""), m.get("real_name", "")]
            for n in names + [m.get("handle", "")]:
                if n:
                    self._strong.setdefault(" ".join(n.casefold().split()), set()).add(m["id"])
            for n in names:
                if n and n.strip():
                    self._weak.setdefault(n.casefold().split()[0], set()).add(m["id"])

    def lookup(self, name: str) -> str | None:
        name = name.strip().lstrip("@")
        tag = _USER_TAG_RE.fullmatch(name)
        if tag or name in self._ids:
            uid = tag.group(1) if tag else name
            return uid if uid in self._ids else None
        key = " ".join(name.casefold().split())
        if not key or key in _RESERVED:
            return None
        for table in (self._strong, self._weak):
            ids = table.get(key)
            if ids:
                return next(iter(ids)) if len(ids) == 1 else None
        return None

    def _resolve_at(self, segment: str, start: int) -> tuple[int, str] | None:
        line_end = segment.find("\n", start)
        window = segment[start + 1: line_end if line_end != -1 else len(segment)]
        words = list(_WORD_RE.finditer(window))[:4]
        for count in range(len(words), 0, -1):
            candidate = window[: words[count - 1].end()]
            stripped = candidate.rstrip(_TRAILING_PUNCT)
            variants = [candidate, stripped]
            for suffix in ("'s", "’s"):
                if stripped.endswith(suffix):
                    variants.append(stripped[: -len(suffix)])
            for variant in dict.fromkeys(v for v in variants if v):
                uid = self.lookup(variant)
                if uid:
                    return start + 1 + len(variant), uid
        return None

    def tag_text(self, text: str, broadcast: str = "") -> tuple[str, list[str], list[str], bool]:
        """``(text with <@UID> tags, tagged IDs in order, unresolved @names, broadcast used)``.

        With ``broadcast`` set, the first plain ``@channel``/``@here`` matching it becomes the real
        ``<!…>`` broadcast. Raw ``<!…>`` broadcast syntax is always defused to plain text."""
        tagged: list[str] = []
        unresolved: list[str] = []
        state = {"broadcast": broadcast, "used": False}
        out: list[str] = []
        pos = 0
        for match in _PROTECTED_RE.finditer(text):
            out.append(self._tag_segment(text[pos:match.start()], tagged, unresolved, state))
            entity = match.group(0)
            tag = _USER_TAG_RE.fullmatch(entity)
            raw = _RAW_BROADCAST_RE.match(entity)
            if tag:
                if tag.group(1) in self._ids:
                    tagged.append(tag.group(1))
                else:
                    unresolved.append(entity)
            elif raw:
                label = raw.group(2) or ("@group" if raw.group(1).startswith("subteam") else "@" + raw.group(1))
                entity = label if label.startswith("@") else "@" + label
            out.append(entity)
            pos = match.end()
        out.append(self._tag_segment(text[pos:], tagged, unresolved, state))
        return "".join(out), list(dict.fromkeys(tagged)), unresolved, state["used"]

    def _tag_segment(self, segment: str, tagged: list[str], unresolved: list[str], state: dict) -> str:
        out: list[str] = []
        pos = 0
        for match in _AT_RE.finditer(segment):
            if match.start() < pos:
                continue
            word = _WORD_RE.match(segment, match.start() + 1)
            keyword = word.group(0).rstrip(_TRAILING_PUNCT).casefold() if word else ""
            if state["broadcast"] and not state["used"] and keyword == state["broadcast"]:
                out.append(segment[pos:match.start()])
                out.append(f"<!{keyword}>")
                state["used"] = True
                pos = match.start() + 1 + len(keyword)
                continue
            resolved = self._resolve_at(segment, match.start())
            if not resolved:
                word = _WORD_RE.match(segment, match.start() + 1)
                name = word.group(0).rstrip(_TRAILING_PUNCT) if word else ""
                if name and name.casefold() not in _RESERVED:
                    unresolved.append("@" + name)
                continue
            end, uid = resolved
            out.append(segment[pos:match.start()])
            out.append(f"<@{uid}>")
            tagged.append(uid)
            pos = end
        out.append(segment[pos:])
        return "".join(out)


def sdk_call_factory(token: str) -> SlackCall:
    """A ``call`` backed by ``slack_sdk.WebClient`` with rate-limit and connection retries."""
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
    from slack_sdk.http_retry.builtin_handlers import (
        ConnectionErrorRetryHandler,
        RateLimitErrorRetryHandler,
    )

    client = WebClient(
        token=token,
        timeout=15,
        retry_handlers=[ConnectionErrorRetryHandler(max_retry_count=2),
                        RateLimitErrorRetryHandler(max_retry_count=3)],
    )

    def call(method: str, **params) -> dict:
        try:
            if method in _WRITE_METHODS:
                return client.api_call(method, json=params).data
            params = {k: ("true" if v else "false") if isinstance(v, bool) else v for k, v in params.items()}
            return client.api_call(method, http_verb="GET", params=params).data
        except SlackApiError as exc:
            data = exc.response.data if exc.response is not None else {}
            raise SlackLookupError(data.get("error", "unknown_error"), data.get("needed", "")) from None

    return call
