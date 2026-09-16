from __future__ import annotations

from mc_version_watcher.formatters import (
    format_delivery_summary,
    format_latest,
    format_test_update,
    format_update_message,
    format_usage,
)
from mc_version_watcher.models import VersionInfo


def test_format_latest_lists_enabled_types_independently() -> None:
    text = format_latest(
        {
            "release": VersionInfo("26.3", "release", "2026-01-01T00:00:00Z"),
            "snapshot": VersionInfo("26.3-rc-3", "snapshot"),
        }
    )
    assert "Minecraft 最新版本" in text
    assert "Release：26.3（正式版）" in text
    assert "Snapshot：26.3-rc-3（Release Candidate）" in text


def test_format_update_message_contains_source_and_optional_time() -> None:
    text = format_update_message(
        [VersionInfo("26.3", "release", "2026-01-01T00:00:00Z")]
    )
    assert "Minecraft 版本更新" in text
    assert "版本：26.3" in text
    assert "分类：Release（正式版）" in text
    assert "发布时间：2026-01-01T00:00:00Z" in text
    assert "Mojang 官方版本清单" in text


def test_format_test_update_is_visibly_synthetic() -> None:
    text = format_test_update()
    assert "测试模拟" in text
    assert "mc-version-watcher-test" in text


def test_format_delivery_summary_reports_successes_and_failures() -> None:
    text = format_delivery_summary(1, [("bad-umo", "offline")])
    assert "成功 1" in text
    assert "失败 1" in text
    assert "bad-umo" in text
    assert "offline" in text


def test_format_usage_lists_all_commands() -> None:
    text = format_usage()
    assert "/mcversion latest" in text
    assert "/mcversion umo" in text
    assert "/mcversion test" in text
