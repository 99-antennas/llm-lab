"""Recent channel activity across the top level and every active thread, as one compact digest.

Hermes keeps one conversation per thread (and per person at the channel's top level unless
``group_sessions_per_user: false``), and messages Shack doesn't answer never enter any of them.
The digest is injected each turn so Shack knows what was said elsewhere in the channel.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone

_TAG_RE = re.compile(r"<@([UW][A-Z0-9]+)(?:\|[^>]*)?>")
_LINK_RE = re.compile(r"<(https?://[^|>]+)\|([^>]+)>")
_BARE_LINK_RE = re.compile(r"<(https?://[^|>]+)>")
_CHANNEL_REF_RE = re.compile(r"<#[CG][A-Z0-9]+\|([^>]*)>")
_BROADCAST_RE = re.compile(r"<!(channel|here|everyone)(?:\|[^>]*)?>")
MAX_THREADS = 10


def _clean(text: str, names: Callable[[str], str], limit: int) -> str:
    text = _TAG_RE.sub(lambda m: "@" + names(m.group(1)), text or "")
    text = _LINK_RE.sub(lambda m: f"{m.group(2)} ({m.group(1)})", text)
    text = _BARE_LINK_RE.sub(lambda m: m.group(1), text)
    text = _CHANNEL_REF_RE.sub(lambda m: "#" + m.group(1), text)
    text = _BROADCAST_RE.sub(lambda m: "@" + m.group(1), text)
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def collect(call: Callable[..., dict], channel_id: str, oldest: float) -> list[dict]:
    """Top-level messages since ``oldest`` plus replies in threads active since then."""
    history = call("conversations.history", channel=channel_id, oldest=f"{oldest:.6f}",
                   limit=100).get("messages") or []
    messages = list(history)
    active = sorted(
        (m for m in history if m.get("reply_count") and float(m.get("latest_reply") or 0) >= oldest),
        key=lambda m: float(m.get("latest_reply") or 0), reverse=True)[:MAX_THREADS]
    # Threads started before the window can still be active; their roots aren't in `history`.
    for root in active:
        replies = call("conversations.replies", channel=channel_id, ts=root["ts"],
                       oldest=f"{oldest:.6f}", limit=100).get("messages") or []
        messages.extend(r for r in replies if r.get("ts") != root["ts"])
    seen, unique = set(), []
    for m in messages:
        if m.get("ts") not in seen and not m.get("subtype") in {"channel_join", "channel_leave"}:
            seen.add(m.get("ts"))
            unique.append(m)
    return sorted(unique, key=lambda m: float(m.get("ts") or 0))


def format_digest(
    messages: list[dict],
    channel_name: str,
    own_id: str,
    names: Callable[[str], str],
    tz,
    hours: float,
    current_thread: str = "",
    exclude_ts: str = "",
    max_messages: int = 60,
    max_chars: int = 8000,
    per_message_chars: int = 280,
) -> str:
    roots = {m["ts"]: m for m in messages if m.get("reply_count")}
    lines: list[str] = []
    for m in messages[-max_messages:]:
        if m.get("ts") == exclude_ts:
            continue
        uid = m.get("user") or ""
        who = "Shack (you)" if uid and uid == own_id else (names(uid) if uid else
                                                           (m.get("username") or "a bot"))
        when = datetime.fromtimestamp(float(m["ts"]), tz).strftime("%a %H:%M")
        thread_ts = m.get("thread_ts")
        if thread_ts and thread_ts != m["ts"]:
            if thread_ts == current_thread:
                where = " [this thread]"
            else:
                root = roots.get(thread_ts)
                topic = _clean(root.get("text", ""), names, 40) if root else ""
                where = f" [in thread: {topic}]" if topic else " [in a thread]"
        else:
            where = " [this thread's first message]" if m["ts"] == current_thread else ""
        lines.append(f"- {when} {who}{where}: {_clean(m.get('text') or '', names, per_message_chars)}")
    if not lines:
        return ""
    header = (f"[Recent activity in #{channel_name} across the channel and all its threads, last "
              f"{hours:g}h, oldest first. It includes messages that weren't for you. Use it as "
              "background so you know what's going on; don't reply to those messages unless "
              "someone asks.]")
    while lines and len(header) + sum(len(line) + 1 for line in lines) > max_chars:
        lines.pop(0)
    return header + "\n" + "\n".join(lines)


class ActivityCache:
    """Per-channel cache of collected messages, so a burst of turns makes one set of API calls."""

    def __init__(self, ttl_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic):
        self._ttl, self._clock = ttl_seconds, clock
        self._lock = threading.Lock()
        self._entries: dict[tuple[str, float], tuple[float, list[dict]]] = {}

    def get(self, call: Callable[..., dict], channel_id: str, hours: float, now: float) -> list[dict]:
        key = (channel_id, hours)
        with self._lock:
            entry = self._entries.get(key)
            if entry and self._clock() - entry[0] < self._ttl:
                return entry[1]
        messages = collect(call, channel_id, now - hours * 3600)
        with self._lock:
            self._entries[key] = (self._clock(), messages)
        return messages


def default_tz():
    try:
        from zoneinfo import ZoneInfo

        try:
            from hermes_cli.config import load_config

            name = (load_config() or {}).get("timezone")
        except Exception:  # noqa: BLE001 - outside Hermes, or config unreadable
            name = None
        return ZoneInfo(name) if name else timezone.utc
    except Exception:  # noqa: BLE001
        return timezone.utc
