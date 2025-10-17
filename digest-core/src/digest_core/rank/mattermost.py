"""Scoring helpers for Mattermost action-first digest."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence
import math

from digest_core.config import MattermostConfig, MattermostScoringWeights
from digest_core.normalize.mattermost import NormalizedMattermostMessage


@dataclass(frozen=True)
class ThreadScoreBreakdown:
    """Detailed breakdown for explainability."""

    mention: float
    dm: float
    private_channel: float
    deadline: float
    action: float
    engagement: float
    recency: float

    @property
    def total(self) -> float:
        return (
            self.mention
            + self.dm
            + self.private_channel
            + self.deadline
            + self.action
            + self.engagement
            + self.recency
        )


def _mention_signal(messages: Sequence[NormalizedMattermostMessage]) -> float:
    score = 0.0
    for message in messages:
        if message.aliases_matched:
            score += 5.0
        for mention in message.mentions:
            if mention.lower() in {"@channel", "@here"}:
                score += 2.0
    return score


def _deadline_signal(messages: Sequence[NormalizedMattermostMessage]) -> float:
    return float(sum(1 for message in messages if message.has_deadline))


def _action_signal(messages: Sequence[NormalizedMattermostMessage]) -> float:
    return float(sum(1 for message in messages if message.has_action_verb))


def _engagement_signal(messages: Sequence[NormalizedMattermostMessage]) -> float:
    # Without full metadata rely on thread length and simple log scaling
    return min(3.0, math.log1p(len(messages)))


def _recency_signal(messages: Sequence[NormalizedMattermostMessage], now: datetime) -> float:
    latest = max((message.created_at for message in messages), default=now)
    delta = max((now - latest).total_seconds(), 0.0)
    hours = delta / 3600 if delta else 0.0
    return math.exp(-hours / 12.0) * 3.0


def score_thread(
    messages: Sequence[NormalizedMattermostMessage],
    *,
    config: MattermostConfig,
    now: datetime | None = None,
) -> ThreadScoreBreakdown:
    """Compute explainable score breakdown for Mattermost thread."""

    if not messages:
        empty = ThreadScoreBreakdown(0, 0, 0, 0, 0, 0, 0)
        return empty

    now = now or datetime.now(timezone.utc)
    weights: MattermostScoringWeights = config.scoring

    mention_component = weights.mention * _mention_signal(messages)
    dm_component = weights.dm * (
        1.0 if any(message.privacy == "dm" for message in messages) else 0.0
    )
    private_component = weights.private_channel * (
        1.0 if any(message.privacy == "private" for message in messages) else 0.0
    )
    deadline_component = weights.deadline * _deadline_signal(messages)
    action_component = weights.action * _action_signal(messages)
    engagement_component = weights.engagement * _engagement_signal(messages)
    recency_component = weights.recency * _recency_signal(messages, now)

    return ThreadScoreBreakdown(
        mention=mention_component,
        dm=dm_component,
        private_channel=private_component,
        deadline=deadline_component,
        action=action_component,
        engagement=engagement_component,
        recency=recency_component,
    )


def thread_score_total(
    messages: Sequence[NormalizedMattermostMessage],
    *,
    config: MattermostConfig,
    now: datetime | None = None,
) -> float:
    """Convenience helper returning total score only."""

    breakdown = score_thread(messages, config=config, now=now)
    return breakdown.total


__all__ = [
    "ThreadScoreBreakdown",
    "score_thread",
    "thread_score_total",
]
