from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from astrbot.api import logger

from .client import ManifestClient
from .formatters import format_test_update, format_update_message
from .models import VersionInfo, VersionManifest
from .state import WatchState


SendText = Callable[[str, str], Awaitable[bool]]
SaveState = Callable[[WatchState], None]


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    target: str
    success: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class CheckResult:
    new_versions: tuple[VersionInfo, ...]
    deliveries: tuple[DeliveryResult, ...]
    baseline_created: bool

    @property
    def success_count(self) -> int:
        return sum(result.success for result in self.deliveries)

    @property
    def failures(self) -> list[tuple[str, str]]:
        return [
            (result.target, result.error or "发送失败")
            for result in self.deliveries
            if not result.success
        ]


class VersionWatcherService:
    def __init__(
        self,
        *,
        client: ManifestClient,
        state: WatchState,
        enabled_types: Sequence[str],
        push_umos: Sequence[str],
        send_text: SendText,
        save_state: SaveState,
    ) -> None:
        self.client = client
        self.state = state
        self.enabled_types = tuple(enabled_types)
        self.push_umos = tuple(push_umos)
        self.send_text = send_text
        self.save_state = save_state

    async def check_once(self) -> CheckResult:
        manifest = await self.client.fetch_manifest()
        selected = [
            version
            for version in manifest.versions
            if version.type in self.enabled_types
        ]
        new_version_keys: set[tuple[str, str]] = set()
        baseline_created = False
        for version_type in self.enabled_types:
            current_ids = {
                version.id for version in selected if version.type == version_type
            }
            if version_type not in self.state.initialized_types:
                self.state.initialized_types.add(version_type)
                self.state.seen_versions[version_type] = set(current_ids)
                baseline_created = True
                continue
            known_ids = self.state.seen_versions.setdefault(version_type, set())
            new_version_keys.update(
                (version_type, version.id)
                for version in selected
                if version.type == version_type and version.id not in known_ids
            )
            known_ids.update(current_ids)

        new_versions = [
            version
            for version in selected
            if (version.type, version.id) in new_version_keys
        ]
        deliveries: tuple[DeliveryResult, ...] = ()
        if new_versions and self.push_umos:
            deliveries = await self._deliver(
                format_update_message(new_versions),
            )
        self.save_state(self.state)
        return CheckResult(tuple(new_versions), deliveries, baseline_created)

    async def send_synthetic_test(self) -> CheckResult:
        deliveries = await self._deliver(format_test_update())
        return CheckResult((), deliveries, False)

    async def _deliver(self, text: str) -> tuple[DeliveryResult, ...]:
        results: list[DeliveryResult] = []
        for target in self.push_umos:
            try:
                accepted = await self.send_text(target, text)
                if not accepted:
                    raise RuntimeError("平台未接受消息")
            except Exception as exc:
                logger.warning(
                    "Minecraft version push failed for %s: %s",
                    target,
                    exc,
                )
                results.append(DeliveryResult(target, False, str(exc)))
            else:
                results.append(DeliveryResult(target, True))
        return tuple(results)


def latest_versions(
    manifest: VersionManifest,
    enabled_types: Sequence[str],
) -> dict[str, VersionInfo | None]:
    return {
        version_type: next(
            (
                version
                for version in manifest.versions
                if version.type == version_type
            ),
            None,
        )
        for version_type in enabled_types
    }
