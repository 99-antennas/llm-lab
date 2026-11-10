import json
import sqlite3

import pytest

from hermes_scripts.retreat_plan_source import SKIP, build_output, fit

CHANNEL = "C0CF5QW6YM6"


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "state.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE sessions (id TEXT, chat_id TEXT, end_reason TEXT, ended_at REAL);
        CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT);
        """
    )
    conn.commit()
    conn.close()
    return path


def add_session(
    db, session_id, *, chat_id=CHANNEL, end_reason=None, ended_at=None, messages=()
):
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO sessions VALUES (?, ?, ?, ?)",
        (session_id, chat_id, end_reason, ended_at),
    )
    conn.executemany(
        "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
        [(session_id, role, content) for role, content in messages],
    )
    conn.commit()
    conn.close()


def test_skips_agent_when_nothing_was_compacted(db, tmp_path):
    add_session(db, "live", messages=[("user", "hi")])
    add_session(
        db, "other-channel", chat_id="C999", end_reason="compression", ended_at=1
    )
    assert build_output(db, tmp_path / "state.json") == SKIP


def test_emits_each_compacted_session_once(db, tmp_path):
    state = tmp_path / "plan" / "state.json"
    add_session(
        db,
        "s1",
        end_reason="compression",
        ended_at=1,
        messages=[
            ("user", "[Kas] Let's book the cabin for May 2-4"),
            ("tool", "ignored tool output"),
            ("assistant", "Noted: cabin May 2-4."),
            ("user", json.dumps([{"type": "text", "text": "[Ray] I'll handle food"}])),
            ("assistant", ""),
        ],
    )
    out = build_output(db, state)
    assert out.splitlines() == [
        "--- conversation segment s1 ---",
        "[channel] [Kas] Let's book the cabin for May 2-4",
        "[Shack] Noted: cabin May 2-4.",
        "[channel] [Ray] I'll handle food",
    ]
    assert json.loads(state.read_text()) == ["s1"]
    assert build_output(db, state) == SKIP

    add_session(
        db, "s2", end_reason="compression", ended_at=2, messages=[("user", "new")]
    )
    assert build_output(db, state).splitlines() == [
        "--- conversation segment s2 ---",
        "[channel] new",
    ]


def test_does_not_write_to_state_db(db, tmp_path):
    add_session(
        db, "s1", end_reason="compression", ended_at=1, messages=[("user", "x")]
    )
    db.chmod(0o444)
    try:
        assert "[channel] x" in build_output(db, tmp_path / "state.json")
    finally:
        db.chmod(0o644)


def test_fit_keeps_head_and_most_recent_lines():
    lines = ["--- header ---", "summary", *[f"msg {i:02d}" for i in range(20)]]
    trimmed = fit(lines, limit=60)
    assert trimmed[:3] == ["--- header ---", "summary", "…[earlier messages omitted]"]
    assert trimmed[-1] == "msg 19"
    assert (
        sum(len(line) + 1 for line in trimmed)
        <= 60 + len("…[earlier messages omitted]") + 1
    )
    assert fit(lines[:3], limit=10_000) == lines[:3]
