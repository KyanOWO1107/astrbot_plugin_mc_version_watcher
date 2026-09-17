from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path

from astrbot.api import logger as astrbot_logger

from mc_version_watcher.models import VersionInfo, VersionManifest
from mc_version_watcher.service import VersionWatcherService
from mc_version_watcher.state import WatchState


def test_service_uses_only_astrbot_api_logger() -> None:
    service_source = (
        Path(__file__).resolve().parents[1] / "mc_version_watcher" / "service.py"
    ).read_text(encoding="utf-8")

    from mc_version_watcher import service

    assert "from astrbot.api import logger" in service_source
    assert "import logging" not in service_source
    assert "logging.getLogger" not in service_source
    assert service.logger is astrbot_logger


class FakeClient:
    def __init__(self, manifests: list[VersionManifest]) -> None:
        self.manifests = iter(manifests)

    async def fetch_manifest(self) -> VersionManifest:
        return next(self.manifests)


def _manifest(*versions: VersionInfo) -> VersionManifest:
    return VersionManifest(tuple(versions))


def _service(client, state, calls, saved, sender):
    return VersionWatcherService(
        client=client,
        state=state,
        enabled_types=("release", "snapshot"),
        push_umos=("aiocqhttp:GroupMessage:100", "aiocqhttp:FriendMessage:200"),
        send_text=sender,
        save_state=lambda current: saved.append(deepcopy(current)),
    )


def test_first_check_creates_baseline_without_sending() -> None:
    calls = []
    saved = []

    async def sender(target: str, text: str) -> bool:
        calls.append((target, text))
        return True

    service = _service(
        FakeClient(
            [
                _manifest(
                    VersionInfo("26.3", "release"),
                    VersionInfo("26w14a", "snapshot"),
                )
            ]
        ),
        WatchState.empty(),
        calls,
        saved,
        sender,
    )

    result = asyncio.run(service.check_once())

    assert result.new_versions == ()
    assert calls == []
    assert saved[-1].initialized_types == {"release", "snapshot"}


def test_second_check_sends_one_combined_message_for_new_versions() -> None:
    calls = []
    saved = []

    async def sender(target: str, text: str) -> bool:
        calls.append((target, text))
        return True

    service = _service(
        FakeClient(
            [
                _manifest(VersionInfo("26.3", "release")),
                _manifest(
                    VersionInfo("26.4", "release"),
                    VersionInfo("26.3", "release"),
                ),
            ]
        ),
        WatchState.empty(),
        calls,
        saved,
        sender,
    )

    asyncio.run(service.check_once())
    result = asyncio.run(service.check_once())

    assert [version.id for version in result.new_versions] == ["26.4"]
    assert len(calls) == 2
    assert all("26.4" in text for _, text in calls)


def test_send_failure_does_not_block_other_targets_or_crash_check() -> None:
    calls = []
    saved = []

    async def sender(target: str, text: str) -> bool:
        calls.append(target)
        if target.endswith(":200"):
            raise RuntimeError("offline")
        return True

    state = WatchState(
        initialized_types={"release"},
        seen_versions={"release": {"26.3"}},
    )
    service = _service(
        FakeClient([_manifest(VersionInfo("26.4", "release"))]),
        state,
        calls,
        saved,
        sender,
    )

    result = asyncio.run(service.check_once())

    assert calls == [
        "aiocqhttp:GroupMessage:100",
        "aiocqhttp:FriendMessage:200",
    ]
    assert result.success_count == 1
    assert result.failures == [("aiocqhttp:FriendMessage:200", "offline")]
    assert saved[-1].seen_versions["release"] == {"26.3", "26.4"}


def test_synthetic_test_push_uses_sender_but_does_not_change_state() -> None:
    calls = []
    state = WatchState(
        initialized_types={"release"},
        seen_versions={"release": {"26.3"}},
    )
    original = deepcopy(state)

    async def sender(target: str, text: str) -> bool:
        calls.append((target, text))
        return True

    service = _service(FakeClient([]), state, calls, [], sender)

    result = asyncio.run(service.send_synthetic_test())

    assert len(calls) == 2
    assert all("测试模拟" in text for _, text in calls)
    assert state == original
    assert result.success_count == 2
