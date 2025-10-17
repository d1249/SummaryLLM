"""Normalization utilities for Mattermost posts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence, Set
import re

from digest_core.config import MattermostConfig
from digest_core.ingest.mm import RawMattermostPost

MENTION_PATTERN = re.compile(r"(?P<mention>@[\w.\-]+)")
HASHTAG_PATTERN = re.compile(r"(?P<tag>#[\w\-]+)")
DEADLINE_PATTERN = re.compile(
    r"\b(до\s+\d{1,2}[:.]\d{2}|до\s+\d{1,2}[./]\d{1,2}|сегодня|завтра|today|tomorrow|\d{1,2}[./]\d{1,2})",
    re.IGNORECASE,
)
ACTION_VERBS = {
    "нужно",
    "сделай",
    "сделать",
    "проверь",
    "проверить",
    "апрув",
    "approve",
    "подтверди",
    "подтвердить",
    "согласуй",
    "согласовать",
    "ответь",
    "ответить",
    "загрузи",
    "загрузить",
    "перешли",
    "переслать",
    "предоставь",
    "предоставить",
}


@dataclass(frozen=True)
class NormalizedMattermostMessage:
    """Canonical Mattermost message representation."""

    id: str
    team_id: str
    channel_id: str
    channel_name: str
    channel_privacy: str
    author_id: str
    author_display: str
    created_at: datetime
    root_id: Optional[str]
    permalink: str
    text: str
    mentions: List[str]
    hashtags: List[str]
    privacy: str
    source: str
    has_deadline: bool
    has_action_verb: bool
    aliases_matched: List[str]


def _normalize_alias(alias: str) -> str:
    alias = alias.strip()
    if alias.startswith("@"):  # Keep canonical form with leading @
        return alias.lower()
    return f"@{alias.lower()}"


def _find_mentions(text: str) -> List[str]:
    return [match.group("mention") for match in MENTION_PATTERN.finditer(text or "")]


def _find_hashtags(text: str) -> List[str]:
    return [match.group("tag") for match in HASHTAG_PATTERN.finditer(text or "")]


def _has_deadline_signal(text: str) -> bool:
    if not text:
        return False
    return bool(DEADLINE_PATTERN.search(text))


def _has_action_signal(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(verb in lowered for verb in ACTION_VERBS)


def _match_aliases(text: str, aliases: Sequence[str]) -> List[str]:
    if not text or not aliases:
        return []
    normalized_aliases: Set[str] = {_normalize_alias(alias) for alias in aliases if alias}
    mentions = _find_mentions(text.lower())
    hits: List[str] = []
    for mention in mentions:
        if mention in normalized_aliases:
            hits.append(mention)
    return hits


def normalize_post(
    post: RawMattermostPost,
    config: MattermostConfig,
    *,
    aliases: Optional[Sequence[str]] = None,
) -> NormalizedMattermostMessage:
    """Normalize raw Mattermost post into canonical structure."""

    aliases = aliases or config.aliases
    mentions = _find_mentions(post.message)
    hashtags = _find_hashtags(post.message)
    alias_hits = _match_aliases(post.message, aliases)

    author_display = post.props.get("override_username") if post.props else None
    if not author_display:
        metadata = post.metadata or {}
        author_display = metadata.get("sender_name")
    author_display = author_display or post.user_id

    return NormalizedMattermostMessage(
        id=post.id,
        team_id=post.team_id,
        channel_id=post.channel_id,
        channel_name=post.channel.name,
        channel_privacy=post.privacy,
        author_id=post.user_id,
        author_display=author_display,
        created_at=post.create_at,
        root_id=post.root_id,
        permalink=post.permalink,
        text=post.message,
        mentions=mentions,
        hashtags=hashtags,
        privacy=post.privacy,
        source="mm",
        has_deadline=_has_deadline_signal(post.message),
        has_action_verb=_has_action_signal(post.message),
        aliases_matched=alias_hits,
    )


__all__ = [
    "NormalizedMattermostMessage",
    "normalize_post",
]
