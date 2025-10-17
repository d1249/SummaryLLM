"""Prompt helpers for Mattermost action-first digest."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Sequence

import structlog

from digest_core.llm.schemas import MattermostLLMResponse
from digest_core.normalize.mattermost import NormalizedMattermostMessage

logger = structlog.get_logger()


def build_action_first_payload(
    unit_id: str,
    messages: Sequence[NormalizedMattermostMessage],
    *,
    privacy: str,
    now: datetime,
    language: str = "ru",
) -> Dict:
    """Build JSON payload for LLM Action-first extraction."""

    posts = []
    for message in messages:
        posts.append(
            {
                "ts": message.created_at.strftime("%H:%M"),
                "author": message.author_display,
                "text": message.text,
                "permalink": message.permalink,
                "channel": message.channel_name,
            }
        )

    payload = {
        "meta": {
            "unit_id": unit_id,
            "privacy": privacy,
            "language": language,
            "now": now.isoformat(),
        },
        "posts": posts,
        "ask": {
            "extract_actions": True,
            "find_deadlines": True,
            "summarize": "short",
            "return_evidence": True,
        },
    }
    return payload


def parse_mattermost_llm_output(raw_json: str) -> MattermostLLMResponse:
    """Parse LLM response into strongly typed structure."""

    try:
        return MattermostLLMResponse.model_validate_json(raw_json)
    except Exception as exc:  # pragma: no cover - error logging path
        logger.error("Failed to parse Mattermost LLM JSON", error=str(exc))
        raise


__all__ = ["build_action_first_payload", "parse_mattermost_llm_output"]
