"""Cron ``--script`` for the retreat-plan updater job.

Hermes compaction ends a session with ``end_reason='compression'`` and continues in a child
session. Each run prints the transcripts of #retreat-planning sessions compacted since the last
run, so the agent can fold them into PLAN.md. With nothing new it prints ``{"wakeAgent": false}``,
which skips the agent entirely (no LLM call, no Slack post).

Reads ``state.db`` read-only; the only write is this job's own processed-sessions file.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/opt/data"))
CHANNEL_ID = os.environ.get("RETREAT_PLAN_CHANNEL_ID", "C0CF5QW6YM6")
PLAN_DIR = HERMES_HOME / "workspace" / "retreat-planning"
MAX_MESSAGE_CHARS = 2000
MAX_TOTAL_CHARS = 60000
SKIP = '{"wakeAgent": false}'


def _message_text(content) -> str:
    """Plain text from a stored message (a string, or a JSON list of content parts)."""
    if not isinstance(content, str):
        return ""
    stripped = content.strip()
    if stripped.startswith("["):
        try:
            parts = json.loads(stripped)
        except ValueError:
            return stripped
        if isinstance(parts, list):
            return "\n".join(
                str(p.get("text", ""))
                for p in parts
                if isinstance(p, dict) and p.get("type") == "text"
            ).strip()
    return stripped


def compacted_sessions(conn: sqlite3.Connection, channel_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT id FROM sessions WHERE chat_id = ? AND end_reason = 'compression' "
        "ORDER BY ended_at, id",
        (channel_id,),
    )
    return [row[0] for row in rows]


def session_lines(conn: sqlite3.Connection, session_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? "
        "AND role IN ('user', 'assistant') ORDER BY id",
        (session_id,),
    )
    lines = []
    for role, content in rows:
        text = _message_text(content)
        if not text:
            continue
        if len(text) > MAX_MESSAGE_CHARS:
            text = text[:MAX_MESSAGE_CHARS] + " …[truncated]"
        lines.append(f"[{'Shack' if role == 'assistant' else 'channel'}] {text}")
    return lines


def fit(
    lines: list[str], limit: int = MAX_TOTAL_CHARS, keep_head: int = 2
) -> list[str]:
    """Keep the opening lines (segment header + first message, which carries the previous
    compaction summary) and as many of the most recent lines as fit, dropping the middle."""
    if sum(len(line) + 1 for line in lines) <= limit or len(lines) <= keep_head:
        return lines
    head = lines[:keep_head]
    budget = limit - sum(len(line) + 1 for line in head)
    tail: list[str] = []
    for line in reversed(lines[keep_head:]):
        if budget - len(line) - 1 < 0:
            break
        tail.append(line)
        budget -= len(line) + 1
    return [*head, "…[earlier messages omitted]", *reversed(tail)]


def load_processed(path: Path) -> set[str]:
    try:
        return set(json.loads(path.read_text()))
    except (OSError, ValueError, TypeError):
        return set()


def save_processed(path: Path, processed: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(sorted(processed)))
    tmp.replace(path)


def build_output(db_path: Path, state_path: Path, channel_id: str = CHANNEL_ID) -> str:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        processed = load_processed(state_path)
        new = [s for s in compacted_sessions(conn, channel_id) if s not in processed]
        if not new:
            return SKIP
        lines: list[str] = []
        for session_id in new:
            lines.append(f"--- conversation segment {session_id} ---")
            lines.extend(session_lines(conn, session_id))
    finally:
        conn.close()
    save_processed(state_path, processed | set(new))
    return "\n".join(fit(lines))


def main() -> int:
    print(build_output(HERMES_HOME / "state.db", PLAN_DIR / ".processed-sessions.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
