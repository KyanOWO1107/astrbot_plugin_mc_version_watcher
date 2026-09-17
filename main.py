from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_PLUGIN_DIR = Path(__file__).resolve().parent
if not __package__ and str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.message_components import Plain
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.core.star.filter.command import GreedyStr

if __package__:
    from .mc_version_watcher.client import ManifestError, MojangManifestClient
    from .mc_version_watcher.formatters import (
        format_delivery_summary,
        format_latest,
        format_usage,
    )
    from .mc_version_watcher.service import VersionWatcherService, latest_versions
    from .mc_version_watcher.state import load_state, save_state
else:
    from mc_version_watcher.client import ManifestError, MojangManifestClient
    from mc_version_watcher.formatters import (
        format_delivery_summary,
        format_latest,
        format_usage,
    )
    from mc_version_watcher.service import VersionWatcherService, latest_versions
    from mc_version_watcher.state import load_state, save_state


PLUGIN_NAME = "astrbot_plugin_mc_version_watcher"
DEFAULT_INTERVAL_MINUTES = 5


@dataclass(frozen=True, slots=True)
class PluginSettings:
    check_interval_minutes: int
    enabled_types: tuple[str, ...]
    push_umos: tuple[str, ...]


def normalize_plugin_config(config: Mapping[str, Any]) -> PluginSettings:
    raw_interval = config.get("check_interval_minutes", DEFAULT_INTERVAL_MINUTES)
    try:
        interval = int(raw_interval)
    except (TypeError, ValueError):
        interval = DEFAULT_INTERVAL_MINUTES
    interval = max(1, interval)

    raw_types = config.get("enabled_version_types", ["release", "snapshot"])
    enabled_types: list[str] = []
    if isinstance(raw_types, (list, tuple)):
        for value in raw_types:
            if value in ("release", "snapshot") and value not in enabled_types:
                enabled_types.append(value)

    raw_umos = config.get("push_umos", [])
    push_umos: list[str] = []
    if isinstance(raw_umos, (list, tuple)):
        for value in raw_umos:
            if isinstance(value, str):
                normalized = value.strip()
                if normalized and normalized not in push_umos:
                    push_umos.append(normalized)

    return PluginSettings(interval, tuple(enabled_types), tuple(push_umos))


@register(
    "astrbot_plugin_mc_version_watcher",
    "Kyan",
    "Minecraft 版本监测",
    "0.1.1",
)
class MinecraftVersionWatcherPlugin(Star):
    def __init__(self, context: Context, config: Mapping[str, Any] | None = None):
        super().__init__(context)
        self.settings = normalize_plugin_config(config or {})
        self.data_dir = StarTools.get_data_dir(PLUGIN_NAME)
        self.state_path = self.data_dir / "state.json"
        self.state = load_state(self.state_path)
        self.client = MojangManifestClient()
        self.service = VersionWatcherService(
            client=self.client,
            state=self.state,
            enabled_types=self.settings.enabled_types,
            push_umos=self.settings.push_umos,
            send_text=self._send_text,
            save_state=lambda current: save_state(self.state_path, current),
        )
        self._poll_task: asyncio.Task[None] | None = None

    async def _send_text(self, umo: str, text: str) -> bool:
        return bool(await self.context.send_message(umo, MessageChain([Plain(text)])))

    async def initialize(self) -> None:
        if self._poll_task is not None and not self._poll_task.done():
            return
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def _poll_loop(self) -> None:
        while True:
            try:
                if self.settings.enabled_types:
                    await self.service.check_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Minecraft version check failed: %s", exc)
            await asyncio.sleep(self.settings.check_interval_minutes * 60)

    async def terminate(self) -> None:
        task = self._poll_task
        if task is None:
            return
        self._poll_task = None
        if task.done():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("Minecraft version watcher task stopped: %s", exc)

    @filter.command("mcversion")
    async def mcversion(self, event: AstrMessageEvent, args: GreedyStr = ""):
        tokens = str(args).strip().lower().split()
        if len(tokens) != 1:
            yield event.plain_result(format_usage())
            return

        command = tokens[0]
        if command == "umo":
            yield event.plain_result(str(event.unified_msg_origin))
            return

        if command == "test":
            if not event.is_admin():
                yield event.plain_result("/mcversion test 仅限管理员使用。")
                return
            if not self.settings.push_umos:
                yield event.plain_result("尚未配置任何推送目标 UMO。")
                return
            result = await self.service.send_synthetic_test()
            yield event.plain_result(
                format_delivery_summary(result.success_count, result.failures)
            )
            return

        if command == "latest":
            try:
                manifest = await self.client.fetch_manifest()
            except ManifestError as exc:
                logger.warning("Minecraft latest command failed: %s", exc)
                yield event.plain_result(f"Minecraft 最新版本获取失败：{exc}")
                return
            except Exception as exc:
                logger.warning("Minecraft latest command failed: %s", exc)
                yield event.plain_result(f"Minecraft 最新版本获取失败：{exc}")
                return
            yield event.plain_result(
                format_latest(latest_versions(manifest, self.settings.enabled_types))
            )
            return

        yield event.plain_result(format_usage())
