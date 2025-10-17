from datetime import datetime, timezone

import pytest

from digest_core.assemble.digest_action_first import (
    ActionDigestAction,
    ActionDigestFYI,
    ActionDigestStats,
    ActionDigestTopic,
    ActionFirstAssembler,
    ActionFirstDigest,
)
from digest_core.config import MattermostConfig
from digest_core.ingest.mm import (
    MattermostChannel,
    MattermostStateStore,
    RawMattermostPost,
    run_ingest_mm,
)
from digest_core.normalize.mattermost import normalize_post
from digest_core.rank.mattermost import score_thread


@pytest.fixture(autouse=True)
def mattermost_token_env(monkeypatch):
    monkeypatch.setenv("MM_TOKEN", "test-token")


def test_mattermost_state_store_roundtrip(tmp_path):
    path = tmp_path / "mm_state.json"
    store = MattermostStateStore(str(path))
    store.update_high_water_mark("channel", 1234)
    store.set_search_hwm("team", 5678)
    store.save()

    restored = MattermostStateStore(str(path))
    restored.load()

    assert restored.get_high_water_mark("channel") == 1234
    assert restored.get_search_hwm("team") == 5678


def _create_raw_post(message: str, channel: MattermostChannel) -> RawMattermostPost:
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    return RawMattermostPost(
        id="post-1",
        channel_id=channel.id,
        team_id=channel.team_id,
        root_id=None,
        user_id="user-1",
        create_at=now,
        update_at=now,
        message=message,
        metadata={},
        props={},
        channel=channel,
        permalink="https://mm.example/pl/post-1",
        privacy=channel.privacy,
    )


def test_normalize_post_extracts_signals():
    channel = MattermostChannel(id="chan", team_id="team", name="ops", type="O")
    post = _create_raw_post("@Elvira нужно подтвердить до 15:00", channel)
    config = MattermostConfig(enabled=True, base_url="https://mm.example", aliases=["@Elvira"])

    normalized = normalize_post(post, config)

    assert normalized.has_deadline is True
    assert normalized.has_action_verb is True
    assert normalized.aliases_matched == ["@elvira"]
    assert "@Elvira" in normalized.mentions


def test_score_thread_with_mentions_and_dm():
    channel = MattermostChannel(id="chan", team_id="team", name="ops", type="D")
    post = _create_raw_post("@elvira подтвердить", channel)
    config = MattermostConfig(enabled=True, base_url="https://mm.example", aliases=["@elvira"])
    normalized = normalize_post(post, config)

    breakdown = score_thread([normalized], config=config, now=datetime(2024, 1, 1, 15, 0, tzinfo=timezone.utc))

    assert breakdown.mention > 0
    assert breakdown.dm > 0
    assert breakdown.total > 0


def test_action_first_assembler_output():
    digest = ActionFirstDigest(
        digest_date="2024-01-02",
        actions=[
            ActionDigestAction(
                channel="incident-core",
                title="Подтвердить апрув",
                quote="@elvira апрув до 15:00",
                permalink="https://mm.example/pl/1",
                instruction="Написать в треде",
                deadline="02.01 15:00",
            )
        ],
        topics=[
            ActionDigestTopic(channel="incident-core", decisions=1, risks=1, summary="Freeze до пятницы")
        ],
        fyi=[ActionDigestFYI(channel="news", summary="Релиз 2.4", permalink="https://mm.example/pl/2")],
        stats=ActionDigestStats(noise_filtered=5, threads_total=3, posts_total=20),
    )

    assembler = ActionFirstAssembler()
    output = assembler.assemble(digest)

    assert "# Мои действия" in output
    assert "[перейти](https://mm.example/pl/1)" in output
    assert "Freeze до пятницы" in output
    assert "отфильтровано 5" in output


def test_run_ingest_mm_with_fake_client(monkeypatch, tmp_path):
    channel = MattermostChannel(id="chan", team_id="team", name="ops", type="O")
    raw_post = _create_raw_post("@elvira проверить отчет", channel)

    class FakeClient:
        def __init__(self, config, session=None):
            self.config = config

        def resolve_team_ids(self, teams):
            return ["team"]

        def list_channels(self, team_id):
            return [channel]

        def fetch_posts_since(self, channel_obj, since_ms, limit):
            return [raw_post]

        def search_mentions(self, team_id, aliases, since_ms=None):
            return []

    monkeypatch.setattr("digest_core.ingest.mm.MattermostClient", FakeClient)

    config = MattermostConfig(
        enabled=True,
        base_url="https://mm.example",
        teams=["team"],
        aliases=["@elvira"],
        max_posts_per_channel=10,
    )

    state = MattermostStateStore(str(tmp_path / "state.json"))
    report = run_ingest_mm(config, now=datetime(2024, 1, 1, tzinfo=timezone.utc), state_store=state)

    assert report.posts_fetched == 1
    assert report.channels_processed == 1
    assert report.posts[0].id == raw_post.id
