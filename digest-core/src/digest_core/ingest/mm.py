"""Mattermost ingest pipeline with high-water mark tracking."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import json

import requests
import structlog

from digest_core.config import MattermostConfig

logger = structlog.get_logger()


class MattermostAPIError(RuntimeError):
    """Raised when Mattermost API returns an unexpected response."""


@dataclass(frozen=True)
class MattermostChannel:
    """Lightweight Mattermost channel representation."""

    id: str
    team_id: str
    name: str
    type: str
    display_name: Optional[str] = None

    @property
    def privacy(self) -> str:
        """Return privacy label based on Mattermost channel type."""

        mapping = {"O": "public", "P": "private", "G": "group", "D": "dm"}
        return mapping.get(self.type, "public")


@dataclass(frozen=True)
class RawMattermostPost:
    """Raw Mattermost post enriched with channel metadata."""

    id: str
    channel_id: str
    team_id: str
    root_id: Optional[str]
    user_id: str
    create_at: datetime
    update_at: datetime
    message: str
    metadata: Dict
    props: Dict
    channel: MattermostChannel
    permalink: str
    privacy: str


@dataclass
class MattermostIngestReport:
    """Aggregate ingest report with raw posts and statistics."""

    posts: List[RawMattermostPost] = field(default_factory=list)
    channels_processed: int = 0
    posts_fetched: int = 0
    skipped_channels: List[str] = field(default_factory=list)
    search_hits: int = 0
    high_water_marks: Dict[str, int] = field(default_factory=dict)


class MattermostStateStore:
    """JSON backed storage for Mattermost high-water marks and metadata."""

    def __init__(self, path: str):
        self.path = Path(path)
        self._data: Dict[str, Dict] = {"channels": {}, "search": {}}

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
                if isinstance(raw, dict):
                    self._data.update(raw)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Failed to read Mattermost state, continuing with empty state",
                path=str(self.path),
                error=str(exc),
            )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(self._data, handle, ensure_ascii=False, indent=2)
        tmp_path.replace(self.path)

    def get_high_water_mark(self, channel_id: str) -> Optional[int]:
        return self._data.get("channels", {}).get(channel_id)

    def update_high_water_mark(self, channel_id: str, timestamp_ms: int) -> None:
        channels = self._data.setdefault("channels", {})
        previous = channels.get(channel_id, 0)
        if timestamp_ms > previous:
            channels[channel_id] = timestamp_ms

    def update_from_posts(self, posts: Iterable[RawMattermostPost]) -> None:
        for post in posts:
            ts_ms = int(post.create_at.timestamp() * 1000)
            self.update_high_water_mark(post.channel_id, ts_ms)

    def set_search_hwm(self, team_id: str, timestamp_ms: int) -> None:
        search = self._data.setdefault("search", {})
        previous = search.get(team_id, 0)
        if timestamp_ms > previous:
            search[team_id] = timestamp_ms

    def get_search_hwm(self, team_id: str) -> Optional[int]:
        return self._data.get("search", {}).get(team_id)


class MattermostClient:
    """Minimal Mattermost REST API client for ingest and delivery."""

    def __init__(
        self,
        config: MattermostConfig,
        *,
        session: Optional[requests.Session] = None,
        timeout: int = 10,
    ):
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout

        token = config.get_token()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        )

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}/api/v4/{path.lstrip('/')}"
        response = self.session.request(method, url, timeout=self.timeout, **kwargs)
        if response.status_code >= 400:
            raise MattermostAPIError(
                f"Mattermost API {method.upper()} {path} failed: {response.status_code} {response.text}"
            )
        return response

    def _request_json(self, method: str, path: str, **kwargs):
        response = self._request(method, path, **kwargs)
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise MattermostAPIError(
                f"Invalid JSON from Mattermost API {path}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Team and channel helpers
    # ------------------------------------------------------------------
    def list_user_teams(self) -> List[Dict]:
        teams: List[Dict] = []
        page = 0
        per_page = 200
        while True:
            params = {"page": page, "per_page": per_page}
            data = self._request_json("get", "users/me/teams", params=params)
            if not data:
                break
            teams.extend(data)
            if len(data) < per_page:
                break
            page += 1
        return teams

    def resolve_team_ids(self, team_refs: List[str]) -> List[str]:
        if not team_refs:
            return []

        teams = self.list_user_teams()
        by_name = {team.get("name"): team.get("id") for team in teams}
        by_display = {team.get("display_name"): team.get("id") for team in teams}

        resolved: List[str] = []
        for ref in team_refs:
            if ref in by_name:
                resolved.append(by_name[ref])
            elif ref in by_display:
                resolved.append(by_display[ref])
            else:
                resolved.append(ref)
        return resolved

    def list_channels(self, team_id: str) -> List[MattermostChannel]:
        channels: List[MattermostChannel] = []
        page = 0
        per_page = 200
        while True:
            params = {"page": page, "per_page": per_page}
            payload = self._request_json(
                "get", f"teams/{team_id}/channels", params=params
            )
            if not payload:
                break
            for raw in payload:
                channel = MattermostChannel(
                    id=raw.get("id"),
                    team_id=team_id,
                    name=raw.get("name", ""),
                    type=raw.get("type", "O"),
                    display_name=raw.get("display_name"),
                )
                channels.append(channel)
            if len(payload) < per_page:
                break
            page += 1
        return channels

    # ------------------------------------------------------------------
    # Post ingestion helpers
    # ------------------------------------------------------------------
    def fetch_posts_since(
        self,
        channel: MattermostChannel,
        *,
        since_ms: int,
        limit: int,
    ) -> List[RawMattermostPost]:
        posts: List[RawMattermostPost] = []
        page = 0
        per_page = 200
        while True:
            params = {
                "page": page,
                "per_page": per_page,
                "since": since_ms,
            }
            payload = self._request_json(
                "get", f"channels/{channel.id}/posts", params=params
            )
            order = payload.get("order", [])
            raw_posts = payload.get("posts", {})
            if not order:
                break

            for post_id in order:
                raw = raw_posts.get(post_id)
                if not raw:
                    continue
                post = self._to_post(channel, raw)
                posts.append(post)
                if len(posts) >= limit:
                    return posts

            if len(order) < per_page:
                break
            page += 1
        return posts

    def fetch_thread(self, root_id: str, channel: MattermostChannel) -> List[RawMattermostPost]:
        payload = self._request_json("get", f"posts/{root_id}/thread")
        order = payload.get("order", [])
        raw_posts = payload.get("posts", {})
        posts: List[RawMattermostPost] = []
        for post_id in order:
            raw = raw_posts.get(post_id)
            if not raw:
                continue
            posts.append(self._to_post(channel, raw))
        return posts

    def search_mentions(
        self,
        team_id: str,
        aliases: List[str],
        *,
        since_ms: Optional[int] = None,
    ) -> List[RawMattermostPost]:
        if not aliases:
            return []
        query = " OR ".join({alias.strip() for alias in aliases if alias.strip()})
        if not query:
            return []

        payload = {"terms": query, "is_or_search": True}
        if since_ms is not None:
            payload["time_zone_offset"] = since_ms
        data = self._request_json(
            "post", f"teams/{team_id}/posts/search", json=payload
        )
        order = data.get("order", [])
        posts_by_id = data.get("posts", {})
        posts: List[RawMattermostPost] = []
        for post_id in order:
            raw = posts_by_id.get(post_id)
            if not raw:
                continue
            channel = MattermostChannel(
                id=raw.get("channel_id", ""),
                team_id=team_id,
                name="",
                type=raw.get("type", "O"),
            )
            posts.append(self._to_post(channel, raw))
        return posts

    def _to_post(self, channel: MattermostChannel, raw: Dict) -> RawMattermostPost:
        def _parse_ts(value: Optional[int]) -> datetime:
            value = value or 0
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc)

        return RawMattermostPost(
            id=raw.get("id", ""),
            channel_id=raw.get("channel_id", channel.id),
            team_id=channel.team_id,
            root_id=raw.get("root_id") or None,
            user_id=raw.get("user_id", ""),
            create_at=_parse_ts(raw.get("create_at")),
            update_at=_parse_ts(raw.get("update_at")),
            message=raw.get("message", ""),
            metadata=raw.get("metadata", {}),
            props=raw.get("props", {}),
            channel=channel,
            permalink=f"{self.base_url}/pl/{raw.get('id', '')}",
            privacy=channel.privacy,
        )


def _channel_matches_filters(
    channel: MattermostChannel,
    *,
    include: List[str],
    exclude: List[str],
    neg_channels: List[str],
) -> bool:
    name = channel.name or ""
    normalized = name.lower()
    normalized_display = (channel.display_name or "").lower()

    # Explicit exclude and neg list take precedence
    if normalized in {c.lower() for c in exclude}:
        return False
    if normalized_display in {c.lower() for c in exclude}:
        return False
    if normalized in {c.lower().lstrip('#') for c in neg_channels}:
        return False
    if normalized_display in {c.lower().lstrip('#') for c in neg_channels}:
        return False

    if include:
        include_norm = {c.lower().lstrip('#') for c in include}
        if normalized not in include_norm and normalized_display not in include_norm:
            return False
    return True


def run_ingest_mm(
    config: MattermostConfig,
    *,
    now: Optional[datetime] = None,
    session: Optional[requests.Session] = None,
    state_store: Optional[MattermostStateStore] = None,
) -> MattermostIngestReport:
    """Run Mattermost ingest returning raw posts and statistics."""

    report = MattermostIngestReport()
    if not config.enabled:
        logger.info("Mattermost ingest disabled")
        return report

    now = now or datetime.now(timezone.utc)
    state_store = state_store or MattermostStateStore(config.state_path)
    state_store.load()

    client = MattermostClient(config, session=session)
    team_ids = client.resolve_team_ids(config.teams)
    lookback_ms = int((now - timedelta(hours=config.lookback_hours)).timestamp() * 1000)

    for team_id in team_ids:
        channels = client.list_channels(team_id)
        for channel in channels:
            if not _channel_matches_filters(
                channel,
                include=config.channels.include,
                exclude=config.channels.exclude,
                neg_channels=config.neg_channels,
            ):
                report.skipped_channels.append(channel.name or channel.id)
                continue

            hwm = state_store.get_high_water_mark(channel.id) or lookback_ms
            posts = client.fetch_posts_since(
                channel,
                since_ms=hwm,
                limit=config.max_posts_per_channel,
            )
            if not posts:
                continue

            report.posts.extend(posts)
            report.posts_fetched += len(posts)
            report.channels_processed += 1
            last_ts = int(max(p.create_at for p in posts).timestamp() * 1000)
            state_store.update_high_water_mark(channel.id, last_ts)
            report.high_water_marks[channel.id] = state_store.get_high_water_mark(
                channel.id
            ) or last_ts

        if config.search.enabled:
            since = state_store.get_search_hwm(team_id) or lookback_ms
            search_posts = client.search_mentions(
                team_id, config.aliases, since_ms=since
            )
            if search_posts:
                report.search_hits += len(search_posts)
                report.posts.extend(search_posts)
                report.posts_fetched += len(search_posts)
                latest = max(int(p.create_at.timestamp() * 1000) for p in search_posts)
                state_store.set_search_hwm(team_id, latest)

    # Persist updated HWM
    state_store.update_from_posts(report.posts)
    state_store.save()

    logger.info(
        "Mattermost ingest completed",
        posts=report.posts_fetched,
        channels=report.channels_processed,
        search_hits=report.search_hits,
    )
    return report


__all__ = [
    "MattermostAPIError",
    "MattermostChannel",
    "RawMattermostPost",
    "MattermostIngestReport",
    "MattermostStateStore",
    "MattermostClient",
    "run_ingest_mm",
]
