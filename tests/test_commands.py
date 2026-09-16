from __future__ import annotations

import asyncio

from main import (
    MinecraftVersionWatcherPlugin,
    PluginSettings,
    normalize_plugin_config,
)
from mc_version_watcher.models import VersionInfo, VersionManifest
from tests.conftest import Plain


class FakeEvent:
    unified_msg_origin = "aiocqhttp:GroupMessage:100"

    def __init__(self, admin: bool = True) -> None:
        self._admin = admin

    def is_admin(self) -> bool:
        return self._admin

    def plain_result(self, text: str) -> str:
        return text


async def collect(async_generator):
    return [item async for item in async_generator]


def test_normalize_plugin_config_applies_defaults_and_filters_values() -> None:
    settings = normalize_plugin_config(
        {
            "check_interval_minutes": 0,
            "enabled_version_types": ["release", "invalid", "release"],
            "push_umos": [" first ", "", "first", 3],
        }
    )
    assert settings == PluginSettings(
        check_interval_minutes=1,
        enabled_types=("release",),
        push_umos=("first",),
    )


def test_umo_command_returns_exact_current_umo() -> None:
    plugin = MinecraftVersionWatcherPlugin.__new__(MinecraftVersionWatcherPlugin)
    result = asyncio.run(collect(plugin.mcversion(FakeEvent(), "umo")))
    assert result == ["aiocqhttp:GroupMessage:100"]


def test_non_admin_test_command_is_rejected() -> None:
    plugin = MinecraftVersionWatcherPlugin.__new__(MinecraftVersionWatcherPlugin)
    result = asyncio.run(collect(plugin.mcversion(FakeEvent(admin=False), "test")))
    assert "管理员" in result[0]


def test_admin_test_command_uses_service_and_returns_summary() -> None:
    plugin = MinecraftVersionWatcherPlugin.__new__(MinecraftVersionWatcherPlugin)

    class FakeService:
        async def send_synthetic_test(self):
            return type(
                "Result",
                (),
                {
                    "success_count": 2,
                    "failures": [],
                },
            )()

    plugin.service = FakeService()
    result = asyncio.run(collect(plugin.mcversion(FakeEvent(), "test")))
    assert "成功 2" in result[0]


def test_latest_command_uses_injected_client() -> None:
    plugin = MinecraftVersionWatcherPlugin.__new__(MinecraftVersionWatcherPlugin)
    plugin.settings = PluginSettings(5, ("release", "snapshot"), ())

    class FakeClient:
        async def fetch_manifest(self):
            return VersionManifest(
                (
                    VersionInfo("26.3", "release"),
                    VersionInfo("26w14a", "snapshot"),
                )
            )

    plugin.client = FakeClient()
    result = asyncio.run(collect(plugin.mcversion(FakeEvent(), "latest")))
    assert "Release：26.3" in result[0]
    assert "Snapshot：26w14a" in result[0]


def test_real_sender_adapter_wraps_text_as_plain_message() -> None:
    calls = []

    class FakeContext:
        async def send_message(self, session, chain):
            calls.append((session, chain))
            return True

    plugin = MinecraftVersionWatcherPlugin.__new__(MinecraftVersionWatcherPlugin)
    plugin.context = FakeContext()
    assert asyncio.run(plugin._send_text("umo", "hello")) is True
    assert calls[0][0] == "umo"
    assert isinstance(calls[0][1][0], Plain)
    assert calls[0][1][0].text == "hello"
