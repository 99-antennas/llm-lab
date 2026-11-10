"""Hermes plugin: make the agent's Slack @mentions real, notifying ``<@UID>`` mentions."""

from __future__ import annotations

import os

from .mentions import MemberDirectory, convert_mentions, roster_prompt

_directory = MemberDirectory(lambda: os.environ.get("SLACK_BOT_TOKEN", "").strip())


def _is_slack(platform) -> bool:
    value = getattr(platform, "value", platform)
    return str(value or "").strip().lower() == "slack"


def _transform_llm_output(response_text: str = "", platform=None, **_kwargs):
    if not _is_slack(platform) or not response_text or "@" not in response_text:
        return None
    converted = convert_mentions(response_text, _directory.get())
    return converted if converted != response_text else None


def _pre_llm_call(platform=None, **_kwargs):
    if not _is_slack(platform):
        return None
    context = roster_prompt(_directory.get())
    return {"context": context} if context else None


def register(ctx) -> None:
    ctx.register_hook("transform_llm_output", _transform_llm_output)
    ctx.register_hook("pre_llm_call", _pre_llm_call)
