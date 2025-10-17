"""Assembler for Mattermost action-first digest template."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class ActionDigestAction:
    """Action item placed in the "My actions" section."""

    channel: str
    title: str
    quote: str
    permalink: str
    instruction: Optional[str] = None
    deadline: Optional[str] = None
    privacy: str = "public"
    urgency: Optional[int] = None
    quote_limit: int = 200


@dataclass(frozen=True)
class ActionDigestTopic:
    """Per-channel/topic summary."""

    channel: str
    decisions: int
    risks: int
    summary: str


@dataclass(frozen=True)
class ActionDigestFYI:
    """FYI item without explicit action."""

    channel: str
    summary: str
    permalink: Optional[str] = None


@dataclass(frozen=True)
class ActionDigestStats:
    """Digest statistics for footer."""

    noise_filtered: int = 0
    threads_total: int = 0
    posts_total: int = 0


@dataclass(frozen=True)
class ActionFirstDigest:
    """Structured digest container for assembly."""

    digest_date: str
    actions: List[ActionDigestAction] = field(default_factory=list)
    topics: List[ActionDigestTopic] = field(default_factory=list)
    fyi: List[ActionDigestFYI] = field(default_factory=list)
    stats: ActionDigestStats = field(default_factory=ActionDigestStats)


class ActionFirstAssembler:
    """Render Action-first digest to Markdown."""

    def assemble(self, digest: ActionFirstDigest) -> str:
        lines: List[str] = []
        lines.append("# Мои действия (Mattermost)")

        if digest.actions:
            for idx, action in enumerate(digest.actions, start=1):
                lines.append(
                    f"{idx}) [#{action.channel}] {action.title}".rstrip()
                )
                quote = action.quote.strip().replace("\n", " ")
                if len(quote) > action.quote_limit:
                    quote = quote[: action.quote_limit - 1].rstrip() + "…"
                lines.append(
                    f"   — Цитата: \"{quote}\" [перейти]({action.permalink})"
                )
                if action.instruction:
                    text = action.instruction.rstrip('.')
                    instruction = f"   — Что сделать: {text}."
                else:
                    instruction = "   — Что сделать: (уточнить действие)"
                if action.deadline:
                    instruction += f" + дедлайн: {action.deadline}"
                lines.append(instruction)
                lines.append("")
        else:
            lines.append("Ничего не требует немедленного внимания.")
            lines.append("")

        lines.append("# Итоги по темам")
        if digest.topics:
            for topic in digest.topics:
                lines.append(
                    f"• #{topic.channel} — {topic.decisions} решений, {topic.risks} рисков; ключ: {topic.summary}"
                )
        else:
            lines.append("• Ничего существенного")
        lines.append("")

        lines.append("# FYI (без действий)")
        if digest.fyi:
            for item in digest.fyi:
                if item.permalink:
                    lines.append(
                        f"• #{item.channel} — {item.summary}; [перейти]({item.permalink})"
                    )
                else:
                    lines.append(f"• #{item.channel} — {item.summary}")
        else:
            lines.append("• Нет дополнительных сообщений")
        lines.append("")

        stats = digest.stats
        lines.append(
            f"_(Источники: MM; отфильтровано {stats.noise_filtered} постов шума; собранно из {stats.threads_total} тредов)_"
        )

        return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "ActionFirstAssembler",
    "ActionFirstDigest",
    "ActionDigestAction",
    "ActionDigestTopic",
    "ActionDigestFYI",
    "ActionDigestStats",
]
