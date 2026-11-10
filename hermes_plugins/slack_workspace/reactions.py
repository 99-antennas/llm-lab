"""What an emoji reaction means as an answer. One table, shared by the activity digest,
``slack_get_replies`` and the tag-reminder script.

👍 / ✅ and friends mean yes, agreed or done; 👎 / ❌ mean no. Anything else (👀, 😂, 🎉…) is shown
for context but is not an answer.
"""

from __future__ import annotations

YES = frozenset({
    "+1", "thumbsup", "white_check_mark", "heavy_check_mark", "ballot_box_with_check",
    "ok_hand", "ok", "100", "raised_hands", "clap", "saluting_face",
})
NO = frozenset({
    "-1", "thumbsdown", "x", "no_entry", "no_entry_sign", "negative_squared_cross_mark",
    "heavy_multiplication_x",
})


def base_name(reaction: str) -> str:
    """``+1::skin-tone-3`` → ``+1``."""
    return (reaction or "").split("::", 1)[0]


def meaning(reaction: str) -> str:
    """``"yes"``, ``"no"`` or ``""`` (not an answer)."""
    name = base_name(reaction)
    return "yes" if name in YES else "no" if name in NO else ""


def answers(message: dict) -> dict[str, list[str]]:
    """``{user_id: [reaction names that answer, …]}`` for reactions on ``message``."""
    out: dict[str, list[str]] = {}
    for reaction in message.get("reactions") or []:
        if meaning(reaction.get("name", "")):
            for user in reaction.get("users") or []:
                out.setdefault(user, []).append(base_name(reaction["name"]))
    return out


def summary(message: dict, names) -> str:
    """``":+1: kas, Ray; :eyes: Nick"`` for the digest (empty when no reactions)."""
    parts = []
    for reaction in message.get("reactions") or []:
        users = ", ".join(names(u) for u in reaction.get("users") or [])
        if users:
            parts.append(f":{base_name(reaction.get('name', ''))}: {users}")
    return "; ".join(parts)
