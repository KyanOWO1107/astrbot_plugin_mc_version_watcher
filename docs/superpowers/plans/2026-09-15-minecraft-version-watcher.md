# Minecraft Version Watcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Create a dependency-light AstrBot plugin that polls Mojang's official Minecraft version manifest, avoids first-run historical spam, reports the latest release and snapshot independently, and pushes new versions to configured UMO targets.

**Architecture:** Keep Mojang parsing, version classification, state persistence, formatting, and polling orchestration outside AstrBot so they can be tested with in-memory fixtures. main.py will be a thin AstrBot adapter that normalizes configuration, owns the lifecycle task, exposes /mcversion commands, and wraps context.send_message(umo, MessageChain([Plain(text)])) as the service text sender.

**Tech Stack:** Python 3.10+, AstrBot plugin API, Python standard-library urllib.request through asyncio.to_thread, JSON state with atomic os.replace, pytest, and dataclasses.

---

## File map

Create the following implementation and test files:

- main.py — AstrBot registration, configuration normalization, lifecycle, command handlers, and the real AstrBot message-sender adapter.
- metadata.yaml — AstrBot plugin metadata for astrbot_plugin_mc_version_watcher version v0.1.0.
- _conf_schema.json — WebUI schema for the 5-minute interval, release/snapshot type list, and UMO target list.
- README.md — installation, configuration, commands, baseline semantics, and manual push verification.
- mc_version_watcher/__init__.py — package marker.
- mc_version_watcher/models.py — immutable VersionInfo/VersionManifest models, supported type constants, manifest URL, and version-label classification.
- mc_version_watcher/client.py — manifest parser and asynchronous Mojang HTTP client.
- mc_version_watcher/state.py — versioned WatchState model and atomic JSON load/save helpers.
- mc_version_watcher/formatters.py — latest, update, test-summary, UMO, and usage text formatters.
- mc_version_watcher/service.py — injectable polling/delivery service and synthetic test-push service.
- tests/__init__.py — test package marker.
- tests/conftest.py — minimal AstrBot module stubs used by command and import tests.
- tests/test_config.py — metadata/schema and configuration-normalization tests.
- tests/test_models.py — model validation and rc/pre classification tests.
- tests/test_client.py — manifest parsing and deterministic transport tests.
- tests/test_state.py — state recovery, deduplication, and atomic-save tests.
- tests/test_formatters.py — exact user-facing formatting tests.
- tests/test_service.py — baseline, new-version, target-isolation, and synthetic-push tests.
- tests/test_commands.py — command behavior, admin gating, and real sender adapter tests.
- tests/test_lifecycle.py — background task startup/cancellation tests.
- tests/test_plugin_import.py — loading main.py from outside the plugin directory with AstrBot stubs.

The plugin has no third-party runtime dependency, so do not add a requirements.txt file solely for this feature.

## Task 1: Scaffold plugin metadata, schema, and test harness

Files:

- Create: tests/__init__.py
- Create: tests/test_config.py
- Create: tests/conftest.py
- Create: metadata.yaml
- Create: _conf_schema.json
- Create: .gitignore

- [ ] Step 1: Write the failing metadata and schema tests

Create tests/test_config.py:

~~~python
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_plugin_metadata_declares_expected_identity() -> None:
    metadata = (ROOT / "metadata.yaml").read_text(encoding="utf-8")
    assert "name: astrbot_plugin_mc_version_watcher" in metadata
    assert "version: v0.1.0" in metadata


def test_configuration_schema_declares_defaults_and_list_options() -> None:
    schema = json.loads((ROOT / "_conf_schema.json").read_text(encoding="utf-8"))

    assert schema["check_interval_minutes"]["type"] == "int"
    assert schema["check_interval_minutes"]["default"] == 5
    assert schema["enabled_version_types"]["type"] == "list"
    assert schema["enabled_version_types"]["default"] == ["release", "snapshot"]
    assert schema["enabled_version_types"]["options"] == ["release", "snapshot"]
    assert schema["push_umos"]["type"] == "list"
    assert schema["push_umos"]["default"] == []
~~~

- [ ] Step 2: Run the focused test and verify the expected red failure

Run:

~~~powershell
python -m pytest tests/test_config.py -q
~~~

Expected: collection or assertion failure because the metadata and schema files do not exist yet.

- [ ] Step 3: Add the minimal AstrBot metadata and WebUI schema

Create metadata.yaml:

~~~yaml
name: astrbot_plugin_mc_version_watcher
display_name: Minecraft Version Watcher
desc: 定时监测 Minecraft 官方版本更新，并向配置的私聊或群聊推送。
version: v0.1.0
author: Kyan
~~~

Create _conf_schema.json:

~~~json
{
  "check_interval_minutes": {
    "description": "Minecraft 版本检查间隔（分钟）",
    "type": "int",
    "default": 5,
    "hint": "最小按 1 分钟处理；默认每 5 分钟检查一次 Mojang 官方版本清单。"
  },
  "enabled_version_types": {
    "description": "需要监测的官方版本类型",
    "type": "list",
    "default": ["release", "snapshot"],
    "options": ["release", "snapshot"],
    "hint": "Release Candidate 和 Pre-release 按 Mojang 官方规范属于 snapshot，并会在消息中额外标注。"
  },
  "push_umos": {
    "description": "版本更新推送目标 UMO 列表",
    "type": "list",
    "default": [],
    "hint": "每项填写一个完整 UMO，可通过 /mcversion umo 获取当前会话 UMO。"
  }
}
~~~

Create .gitignore:

~~~gitignore
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
.cache/
~~~

Create an empty tests/__init__.py.

- [ ] Step 4: Add shared AstrBot test stubs

Create tests/conftest.py with an install_astrbot_stubs helper that inserts the required AstrBot modules into sys.modules before command tests import main:

~~~python
from __future__ import annotations

import sys
import types
from pathlib import Path


class Plain:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeStar:
    def __init__(self, context) -> None:
        self.context = context


def install_astrbot_stubs(data_dir: Path | None = None) -> None:
    modules = {
        name: types.ModuleType(name)
        for name in (
            "astrbot",
            "astrbot.api",
            "astrbot.api.event",
            "astrbot.api.message_components",
            "astrbot.api.star",
            "astrbot.core",
            "astrbot.core.star",
            "astrbot.core.star.filter",
            "astrbot.core.star.filter.command",
        )
    }
    modules["astrbot.api"].AstrBotConfig = dict
    modules["astrbot.api"].logger = types.SimpleNamespace(
        warning=lambda *args, **kwargs: None,
        exception=lambda *args, **kwargs: None,
    )
    modules["astrbot.api.event"].AstrMessageEvent = object
    modules["astrbot.api.event"].filter = types.SimpleNamespace(
        command=lambda _name: lambda function: function,
    )
    modules["astrbot.api.message_components"].Plain = Plain
    modules["astrbot.api.star"].Context = object
    modules["astrbot.api.star"].Star = FakeStar
    modules["astrbot.api.star"].StarTools = types.SimpleNamespace(
        get_data_dir=lambda _name: data_dir or Path(".cache"),
    )
    modules["astrbot.api.star"].register = (
        lambda *_args, **_kwargs: lambda cls: cls
    )
    modules["astrbot.core.star.filter.command"].GreedyStr = str
    sys.modules.update(modules)
~~~

Call install_astrbot_stubs() at the bottom of conftest.py so modules are available during collection.

- [ ] Step 5: Run the focused test and confirm green

Run:

~~~powershell
python -m pytest tests/test_config.py -q
~~~

Expected: 2 passed.

- [ ] Step 6: Commit the scaffold

~~~powershell
git add .gitignore metadata.yaml _conf_schema.json tests
git commit -m "chore: scaffold Minecraft version watcher plugin"
~~~

## Task 2: Add pure version models and official snapshot labels

Files:

- Create: mc_version_watcher/__init__.py
- Create: mc_version_watcher/models.py
- Create: tests/test_models.py

- [ ] Step 1: Write the failing model tests

Create tests/test_models.py:

~~~python
from __future__ import annotations

import pytest

from mc_version_watcher.models import (
    SUPPORTED_VERSION_TYPES,
    VersionInfo,
    classify_version,
)


def test_supported_types_are_release_and_snapshot() -> None:
    assert SUPPORTED_VERSION_TYPES == ("release", "snapshot")


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        (VersionInfo("26.3", "release"), "Release（正式版）"),
        (VersionInfo("26w14a", "snapshot"), "Snapshot（普通快照）"),
        (VersionInfo("1.21.11-rc3", "snapshot"), "Snapshot（Release Candidate）"),
        (VersionInfo("26.3-rc-3", "snapshot"), "Snapshot（Release Candidate）"),
        (VersionInfo("1.21.11-pre5", "snapshot"), "Snapshot（Pre-release）"),
        (VersionInfo("26.3-pre-3", "snapshot"), "Snapshot（Pre-release）"),
    ],
)
def test_classify_version_uses_official_type_and_snapshot_suffix(
    version: VersionInfo,
    expected: str,
) -> None:
    assert classify_version(version) == expected


def test_version_info_rejects_empty_id_or_type() -> None:
    with pytest.raises(ValueError, match="id"):
        VersionInfo("", "release")
    with pytest.raises(ValueError, match="type"):
        VersionInfo("26.3", "")
~~~

- [ ] Step 2: Run the model tests and verify the expected red failure

Run:

~~~powershell
python -m pytest tests/test_models.py -q
~~~

Expected: import failure because mc_version_watcher.models does not exist yet.

- [ ] Step 3: Implement the minimal pure model module

Create an empty mc_version_watcher/__init__.py.

Create mc_version_watcher/models.py:

~~~python
from __future__ import annotations

from dataclasses import dataclass
import re


MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
SUPPORTED_VERSION_TYPES = ("release", "snapshot")
_RC_PATTERN = re.compile(r"-rc(?:-?\d+)?$", re.IGNORECASE)
_PRE_PATTERN = re.compile(r"-pre(?:-?\d+)?$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class VersionInfo:
    id: str
    type: str
    release_time: str | None = None
    url: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("version id must be a non-empty string")
        if not isinstance(self.type, str) or not self.type.strip():
            raise ValueError("version type must be a non-empty string")


@dataclass(frozen=True, slots=True)
class VersionManifest:
    versions: tuple[VersionInfo, ...]


def classify_version(version: VersionInfo) -> str:
    if version.type == "release":
        return "Release（正式版）"
    if version.type != "snapshot":
        return f"{version.type}（未分类）"
    if _RC_PATTERN.search(version.id):
        return "Snapshot（Release Candidate）"
    if _PRE_PATTERN.search(version.id):
        return "Snapshot（Pre-release）"
    return "Snapshot（普通快照）"
~~~

- [ ] Step 4: Run model tests and verify green

Run:

~~~powershell
python -m pytest tests/test_models.py -q
~~~

Expected: 4 passed.

- [ ] Step 5: Commit the model layer

~~~powershell
git add mc_version_watcher tests/test_models.py
git commit -m "feat: add Minecraft version models and labels"
~~~

## Task 3: Parse and fetch Mojang's official manifest

Files:

- Create: mc_version_watcher/client.py
- Create: tests/test_client.py

- [ ] Step 1: Write the failing parser and transport tests

Create tests/test_client.py:

~~~python
from __future__ import annotations

import asyncio

import pytest

from mc_version_watcher.client import (
    ManifestFetchError,
    ManifestParseError,
    MojangManifestClient,
    parse_manifest_payload,
)


def test_parse_manifest_payload_preserves_manifest_order_and_fields() -> None:
    manifest = parse_manifest_payload(
        {
            "latest": {"release": "26.3", "snapshot": "26.3-rc-3"},
            "versions": [
                {
                    "id": "26.3",
                    "type": "release",
                    "url": "https://example.test/release.json",
                    "releaseTime": "2026-01-01T00:00:00+00:00",
                },
                {
                    "id": "26.3-rc-3",
                    "type": "snapshot",
                    "url": "https://example.test/rc.json",
                    "releaseTime": "2025-12-31T00:00:00+00:00",
                },
            ],
        }
    )

    assert [version.id for version in manifest.versions] == ["26.3", "26.3-rc-3"]
    assert manifest.versions[0].release_time == "2026-01-01T00:00:00+00:00"
    assert manifest.versions[1].url == "https://example.test/rc.json"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"versions": "not-a-list"},
        {"versions": [{}]},
        {"versions": [{"id": "26.3"}]},
        {"versions": [{"type": "release"}]},
    ],
)
def test_parse_manifest_payload_rejects_missing_required_structure(payload) -> None:
    with pytest.raises(ManifestParseError):
        parse_manifest_payload(payload)


def test_client_uses_injected_transport_without_live_network() -> None:
    calls: list[tuple[str, float]] = []

    def transport(url: str, timeout: float) -> bytes:
        calls.append((url, timeout))
        return b'{"versions":[{"id":"26.3","type":"release"}]}'

    client = MojangManifestClient(transport=transport, timeout=7.5)
    manifest = asyncio.run(client.fetch_manifest())

    assert manifest.versions[0].id == "26.3"
    assert calls[0][0].endswith("version_manifest_v2.json")
    assert calls[0][1] == 7.5


def test_client_wraps_transport_errors() -> None:
    def transport(_url: str, _timeout: float) -> bytes:
        raise OSError("offline")

    client = MojangManifestClient(transport=transport)
    with pytest.raises(ManifestFetchError, match="offline"):
        asyncio.run(client.fetch_manifest())
~~~

- [ ] Step 2: Run client tests and verify the expected red failure

Run:

~~~powershell
python -m pytest tests/test_client.py -q
~~~

Expected: import failure because mc_version_watcher.client does not exist yet.

- [ ] Step 3: Implement deterministic parsing and the standard-library HTTP client

Create mc_version_watcher/client.py with these interfaces:

~~~python
from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any, Protocol
from urllib.request import Request, urlopen

from .models import MANIFEST_URL, VersionInfo, VersionManifest


class ManifestError(RuntimeError):
    """Base class for official manifest failures."""


class ManifestFetchError(ManifestError):
    pass


class ManifestParseError(ManifestError):
    pass


class ManifestClient(Protocol):
    async def fetch_manifest(self) -> VersionManifest:
        ...


def parse_manifest_payload(payload: Any) -> VersionManifest:
    if not isinstance(payload, dict):
        raise ManifestParseError("manifest root must be an object")
    raw_versions = payload.get("versions")
    if not isinstance(raw_versions, list):
        raise ManifestParseError("manifest versions must be a list")

    versions: list[VersionInfo] = []
    for index, raw_version in enumerate(raw_versions):
        if not isinstance(raw_version, dict):
            raise ManifestParseError(f"manifest version {index} must be an object")
        version_id = raw_version.get("id")
        version_type = raw_version.get("type")
        if not isinstance(version_id, str) or not version_id.strip():
            raise ManifestParseError(f"manifest version {index} has invalid id")
        if not isinstance(version_type, str) or not version_type.strip():
            raise ManifestParseError(f"manifest version {index} has invalid type")
        release_time = raw_version.get("releaseTime")
        if release_time is not None and not isinstance(release_time, str):
            raise ManifestParseError(
                f"manifest version {index} has invalid releaseTime"
            )
        detail_url = raw_version.get("url")
        if detail_url is not None and not isinstance(detail_url, str):
            raise ManifestParseError(f"manifest version {index} has invalid url")
        versions.append(
            VersionInfo(
                id=version_id,
                type=version_type,
                release_time=release_time,
                url=detail_url,
            )
        )
    return VersionManifest(tuple(versions))


def _fetch_bytes(url: str, timeout: float) -> bytes:
    request = Request(
        url,
        headers={"User-Agent": "astrbot-plugin-mc-version-watcher/0.1"},
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read()


class MojangManifestClient:
    def __init__(
        self,
        *,
        url: str = MANIFEST_URL,
        timeout: float = 20.0,
        transport: Callable[[str, float], bytes] | None = None,
    ) -> None:
        self.url = url
        self.timeout = timeout
        self._transport = transport or _fetch_bytes

    async def fetch_manifest(self) -> VersionManifest:
        try:
            raw = await asyncio.to_thread(self._transport, self.url, self.timeout)
            payload = json.loads(raw.decode("utf-8"))
            return parse_manifest_payload(payload)
        except ManifestParseError:
            raise
        except Exception as exc:
            raise ManifestFetchError(str(exc)) from exc
~~~

The parser must keep unknown future type values in the manifest model; the service filters only configured official types. This preserves forward compatibility while keeping release/snapshot behavior explicit.

- [ ] Step 4: Run focused client/model tests and verify green

Run:

~~~powershell
python -m pytest tests/test_models.py tests/test_client.py -q
~~~

Expected: 17 passed.

- [ ] Step 5: Commit the client layer

~~~powershell
git add mc_version_watcher/client.py tests/test_client.py
git commit -m "feat: add Mojang manifest client"
~~~

## Task 4: Add versioned, atomic persistent state

Files:

- Create: mc_version_watcher/state.py
- Create: tests/test_state.py

- [ ] Step 1: Write the failing state tests

Create tests/test_state.py:

~~~python
from __future__ import annotations

import json

from mc_version_watcher.state import WatchState, load_state, save_state


def test_missing_state_is_empty(tmp_path) -> None:
    state = load_state(tmp_path / "state.json")
    assert state.initialized_types == set()
    assert state.seen_versions == {}


def test_malformed_state_is_safely_treated_as_empty(tmp_path) -> None:
    path = tmp_path / "state.json"
    path.write_text("not-json", encoding="utf-8")
    state = load_state(path)
    assert state == WatchState.empty()


def test_save_state_writes_versioned_sorted_json_and_removes_temp_file(tmp_path) -> None:
    path = tmp_path / "nested" / "state.json"
    state = WatchState(
        initialized_types={"snapshot"},
        seen_versions={"snapshot": {"26w14a", "26.3-rc-3"}},
    )

    save_state(path, state)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {
        "schema_version": 1,
        "initialized_types": ["snapshot"],
        "seen_versions": {"snapshot": ["26.3-rc-3", "26w14a"]},
    }
    assert not path.with_suffix(".json.tmp").exists()


def test_load_state_deduplicates_and_normalizes_lists(tmp_path) -> None:
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "initialized_types": ["release", "release", 3],
                "seen_versions": {
                    "release": ["26.3", "26.3", 3],
                    "snapshot": "invalid",
                },
            }
        ),
        encoding="utf-8",
    )

    state = load_state(path)

    assert state.initialized_types == {"release"}
    assert state.seen_versions == {"release": {"26.3"}}
~~~

- [ ] Step 2: Run state tests and verify the expected red failure

Run:

~~~powershell
python -m pytest tests/test_state.py -q
~~~

Expected: import failure because mc_version_watcher.state does not exist yet.

- [ ] Step 3: Implement the minimal state store

Create mc_version_watcher/state.py:

~~~python
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from typing import Any


STATE_SCHEMA_VERSION = 1


@dataclass
class WatchState:
    initialized_types: set[str] = field(default_factory=set)
    seen_versions: dict[str, set[str]] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "WatchState":
        return cls()


def _normalized_state(payload: Any) -> WatchState:
    if not isinstance(payload, dict):
        return WatchState.empty()
    if payload.get("schema_version") != STATE_SCHEMA_VERSION:
        return WatchState.empty()

    initialized = {
        value
        for value in payload.get("initialized_types", [])
        if isinstance(value, str) and value
    }
    raw_seen = payload.get("seen_versions", {})
    seen: dict[str, set[str]] = {}
    if isinstance(raw_seen, dict):
        for version_type, values in raw_seen.items():
            if not isinstance(version_type, str) or not isinstance(values, list):
                continue
            normalized_values = {
                value for value in values if isinstance(value, str) and value
            }
            if normalized_values:
                seen[version_type] = normalized_values
    return WatchState(initialized_types=initialized, seen_versions=seen)


def load_state(path: Path) -> WatchState:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return WatchState.empty()
    return _normalized_state(payload)


def save_state(path: Path, state: WatchState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": STATE_SCHEMA_VERSION,
        "initialized_types": sorted(state.initialized_types),
        "seen_versions": {
            version_type: sorted(values)
            for version_type, values in sorted(state.seen_versions.items())
            if values
        },
    }
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_path, path)
~~~

- [ ] Step 4: Run focused state tests and verify green

Run:

~~~powershell
python -m pytest tests/test_state.py -q
~~~

Expected: 4 passed.

- [ ] Step 5: Commit the state layer

~~~powershell
git add mc_version_watcher/state.py tests/test_state.py
git commit -m "feat: persist watcher baselines atomically"
~~~

## Task 5: Add deterministic user-facing formatters

Files:

- Create: mc_version_watcher/formatters.py
- Create: tests/test_formatters.py

- [ ] Step 1: Write the failing formatter tests

Create tests/test_formatters.py:

~~~python
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
~~~

- [ ] Step 2: Run formatter tests and verify the expected red failure

Run:

~~~powershell
python -m pytest tests/test_formatters.py -q
~~~

Expected: import failure because mc_version_watcher.formatters does not exist yet.

- [ ] Step 3: Implement formatters without AstrBot imports

Create mc_version_watcher/formatters.py with these public functions:

~~~python
from __future__ import annotations

from collections.abc import Mapping, Sequence

from .models import MANIFEST_URL, VersionInfo, classify_version


def _label_suffix(version: VersionInfo) -> str:
    label = classify_version(version)
    return label.split("（", 1)[1].rstrip("）") if "（" in label else label


def format_latest(latest: Mapping[str, VersionInfo | None]) -> str:
    lines = ["Minecraft 最新版本"]
    if not latest:
        return "Minecraft 最新版本\n\n未启用任何版本类型。"
    for version_type, version in latest.items():
        if version is None:
            lines.append(f"{version_type.capitalize()}：当前没有匹配版本")
        else:
            lines.append(
                f"{version_type.capitalize()}：{version.id}（{_label_suffix(version)}）"
            )
    return "\n".join(lines)


def format_update_message(
    versions: Sequence[VersionInfo],
    *,
    test: bool = False,
) -> str:
    title = "Minecraft 版本更新（测试模拟）" if test else "Minecraft 版本更新"
    lines = [title, ""]
    for version in versions:
        lines.extend([f"- 版本：{version.id}", f"  分类：{classify_version(version)}"])
        if version.release_time:
            lines.append(f"  发布时间：{version.release_time}")
        lines.append("")
    lines.extend(["来源：Mojang 官方版本清单", MANIFEST_URL])
    return "\n".join(lines)


def format_test_update() -> str:
    return format_update_message(
        [VersionInfo("mc-version-watcher-test", "snapshot")],
        test=True,
    )


def format_delivery_summary(
    success_count: int,
    failures: Sequence[tuple[str, str]],
) -> str:
    lines = [f"模拟推送完成：成功 {success_count}，失败 {len(failures)}。"]
    for target, error in failures:
        lines.append(f"- {target}：{error}")
    return "\n".join(lines)


def format_usage() -> str:
    return (
        "用法：/mcversion latest | umo | test\n"
        "latest：分别查询已启用类型的最新版本\n"
        "umo：获取当前会话 UMO\n"
        "test：管理员向已配置 UMO 发送模拟更新"
    )
~~~

The public output asserted above must remain stable. format_update_message must not import or instantiate Plain.

- [ ] Step 4: Run focused formatter/model/state tests and verify green

Run:

~~~powershell
python -m pytest tests/test_models.py tests/test_state.py tests/test_formatters.py -q
~~~

Expected: 17 passed.

- [ ] Step 5: Commit the formatter layer

~~~powershell
git add mc_version_watcher/formatters.py tests/test_formatters.py
git commit -m "feat: format version watcher messages"
~~~

## Task 6: Implement polling, baseline, delivery isolation, and synthetic test push

Files:

- Create: mc_version_watcher/service.py
- Create: tests/test_service.py

- [ ] Step 1: Write the failing service tests

Create tests/test_service.py with deterministic fake clients and senders:

~~~python
from __future__ import annotations

import asyncio
from copy import deepcopy

from mc_version_watcher.models import VersionInfo, VersionManifest
from mc_version_watcher.service import VersionWatcherService
from mc_version_watcher.state import WatchState


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

    assert calls == ["aiocqhttp:GroupMessage:100", "aiocqhttp:FriendMessage:200"]
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
~~~

- [ ] Step 2: Run service tests and verify the expected red failure

Run:

~~~powershell
python -m pytest tests/test_service.py -q
~~~

Expected: import failure because mc_version_watcher.service does not exist yet.

- [ ] Step 3: Implement the service interfaces and minimal algorithm

Create mc_version_watcher/service.py with these dataclasses and methods:

~~~python
from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
import logging

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
        logger: logging.Logger | None = None,
    ) -> None:
        self.client = client
        self.state = state
        self.enabled_types = tuple(enabled_types)
        self.push_umos = tuple(push_umos)
        self.send_text = send_text
        self.save_state = save_state
        self.logger = logger or logging.getLogger(__name__)

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
            deliveries = await self._deliver(format_update_message(new_versions))
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
                self.logger.warning(
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
~~~

The implementation must update state only after successful manifest validation. It must persist current IDs even when there are no UMO targets, and it must never call save_state from send_synthetic_test.

- [ ] Step 4: Run focused service/formatter/client/state tests and verify green

Run:

~~~powershell
python -m pytest tests/test_client.py tests/test_state.py tests/test_formatters.py tests/test_service.py -q
~~~

Expected: 22 passed.

- [ ] Step 5: Commit the service layer

~~~powershell
git add mc_version_watcher/service.py tests/test_service.py
git commit -m "feat: detect and deliver new Minecraft versions"
~~~

## Task 7: Integrate AstrBot lifecycle, configuration, and commands

Files:

- Modify: tests/conftest.py
- Create: tests/test_commands.py
- Create: tests/test_lifecycle.py
- Create: main.py

- [ ] Step 1: Write failing configuration and command tests

Create tests/test_commands.py with a FakeEvent whose unified_msg_origin is aiocqhttp:GroupMessage:100, whose is_admin() returns a constructor-selected boolean, and whose plain_result(text) returns text. Add an async collect helper that drains a command async generator.

The tests must cover the following exact behaviors:

~~~python
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
                {"success_count": 2, "failures": []},
            )()

    plugin.service = FakeService()
    result = asyncio.run(collect(plugin.mcversion(FakeEvent(), "test")))
    assert "成功 2" in result[0]
~~~

Also test latest with an injected client returning release 26.3 and snapshot 26w14a, asserting both lines are present. Test _send_text with a FakeContext that records session and chain, asserting the MessageChain contains a Plain with text hello.

Create tests/test_lifecycle.py:

~~~python
from __future__ import annotations

import asyncio

from main import MinecraftVersionWatcherPlugin, PluginSettings


def test_initialize_creates_one_task_and_terminate_cancels_it() -> None:
    async def scenario() -> None:
        plugin = MinecraftVersionWatcherPlugin.__new__(MinecraftVersionWatcherPlugin)
        plugin.settings = PluginSettings(1, (), ())
        plugin._poll_task = None

        async def poll_loop():
            await asyncio.Event().wait()

        plugin._poll_loop = poll_loop
        await plugin.initialize()
        task = plugin._poll_task
        assert task is not None
        await plugin.initialize()
        assert plugin._poll_task is task
        await plugin.terminate()
        assert task.cancelled()
        assert plugin._poll_task is None

    asyncio.run(scenario())
~~~

- [ ] Step 2: Run command/lifecycle tests and verify the expected red failure

Run:

~~~powershell
python -m pytest tests/test_commands.py tests/test_lifecycle.py -q
~~~

Expected: import failure because main.py does not exist yet.

- [ ] Step 3: Implement configuration normalization and AstrBot integration

Create main.py with:

~~~python
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

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
~~~

The MinecraftVersionWatcherPlugin must:

1. Insert its directory into sys.path only when loaded as a top-level file, matching the sibling plugin pattern.
2. Import the pure modules with relative imports when __package__ is set and top-level imports otherwise.
3. Call super().__init__(context), normalize config or {}, get the data directory with StarTools.get_data_dir(PLUGIN_NAME), load state.json, create MojangManifestClient, and create VersionWatcherService with self._send_text and a state-save lambda.
4. Define async _send_text(umo, text) as bool(await self.context.send_message(umo, MessageChain([Plain(text)]))).
5. Define initialize() to create exactly one asyncio.create_task(self._poll_loop()) when no live task exists.
6. Define _poll_loop() to skip network checks when no type is enabled, otherwise call service.check_once() immediately, catch ordinary exceptions with a warning, and then wait check_interval_minutes times 60 seconds. Re-raise asyncio.CancelledError.
7. Define terminate() to cancel the task, await it, suppress asyncio.CancelledError, and clear the task field.
8. Register one @filter.command("mcversion") async-generator command accepting GreedyStr.
9. Parse exactly one lowercase subcommand. latest fetches the manifest, calls latest_versions, and yields event.plain_result(format_latest(...)). umo yields the exact event.unified_msg_origin. test checks event.is_admin(), calls service.send_synthetic_test(), and yields format_delivery_summary(result.success_count, result.failures). Unknown or empty input yields format_usage().
10. Catch ManifestError and ordinary fetch exceptions in latest and return a readable failure result without using stale data.

Register the class as:

~~~python
@register(
    "astrbot_plugin_mc_version_watcher",
    "Kyan",
    "Minecraft 版本监测",
    "0.1.0",
)
class MinecraftVersionWatcherPlugin(Star):
    ...
~~~

- [ ] Step 4: Run command/lifecycle tests and then all unit tests

Run:

~~~powershell
python -m pytest tests/test_commands.py tests/test_lifecycle.py -q
python -m pytest tests/test_models.py tests/test_client.py tests/test_state.py tests/test_formatters.py tests/test_service.py tests/test_commands.py tests/test_lifecycle.py -q
~~~

Expected: the command/lifecycle tests pass first, then all collected tests pass with no warnings about pending tasks.

- [ ] Step 5: Commit the AstrBot adapter

~~~powershell
git add main.py tests/conftest.py tests/test_commands.py tests/test_lifecycle.py
git commit -m "feat: integrate Minecraft watcher with AstrBot"
~~~

## Task 8: Verify package-style imports and document operation

Files:

- Create: tests/test_plugin_import.py
- Create: README.md

- [ ] Step 1: Write the failing external-load test

Create tests/test_plugin_import.py with a subprocess loader that:

1. Creates stub modules for astrbot, astrbot.api, astrbot.api.event, astrbot.api.message_components, astrbot.api.star, and astrbot.core.star.filter.command.
2. Loads the absolute main.py path using importlib.util.spec_from_file_location from a temporary working directory.
3. Executes the module and asserts return code 0 with empty stderr.

The test must pass the absolute main.py path as an argument and must not depend on the current working directory being the plugin directory.

- [ ] Step 2: Run the import test and verify the expected red failure

Run:

~~~powershell
python -m pytest tests/test_plugin_import.py -q
~~~

Expected: failure until the top-level import fallback and all package files are present.

- [ ] Step 3: Add the operational README

Create README.md with these sections and facts:

~~~markdown
# Minecraft Version Watcher

用于 AstrBot 定时监测 Mojang 官方 Minecraft 版本清单并推送更新。

## 功能

- 默认每 5 分钟检查 release 和 snapshot。
- Release Candidate 和 Pre-release 按官方规范归入 snapshot，并在消息中标注。
- 支持配置私聊和群聊 UMO 推送目标。
- 首次检查只建立基线，不推送历史版本。
- 支持 /mcversion latest、/mcversion umo、管理员 /mcversion test。

## 配置

在 AstrBot 插件设置中配置检查间隔、监测类型和推送 UMO 列表。先在目标私聊或群聊中发送 /mcversion umo，再把返回值复制到推送 UMO 列表。

## 命令

- /mcversion latest：分别获取已启用类型的最新版本。
- /mcversion umo：获取当前会话 UMO。
- /mcversion test：管理员向全部配置目标发送真实模拟推送，不访问 Mojang，也不修改版本状态。

## 数据和故障处理

版本来源为 Mojang 官方 manifest：
https://piston-meta.mojang.com/mc/game/version_manifest_v2.json

状态文件位于 AstrBot 的：
data/plugin_data/astrbot_plugin_mc_version_watcher/state.json

网络失败会保留旧状态并在下一周期重试。单个 UMO 发送失败不会阻塞其他目标；失败会记录到日志。

## 开发检查

~~~powershell
python -m pytest -q
python -m compileall -q .
~~~
~~~

Do not document automatic retry semantics that are not implemented, and do not claim that the live Mojang endpoint or a real AstrBot adapter was tested by the offline unit suite.

- [ ] Step 4: Run import, full tests, and compile checks

Run:

~~~powershell
python -m pytest tests/test_plugin_import.py -q
python -m pytest -q
python -m compileall -q .
~~~

Expected: the import test passes, the full test suite passes, and compileall exits with code 0.

- [ ] Step 5: Commit documentation and import verification

~~~powershell
git add README.md tests/test_plugin_import.py
git commit -m "docs: document Minecraft version watcher"
~~~

## Task 9: Final verification and manual acceptance handoff

Files:

- Verify: all tracked files in the repository

- [ ] Step 1: Run the complete automated verification set

Run each command from the repository root:

~~~powershell
python -m pytest -q
python -m compileall -q .
python -c "import json; json.load(open('_conf_schema.json', encoding='utf-8')); print('schema ok')"
git diff --check
git status --short
~~~

Expected:

- pytest reports all tests passed;
- compileall exits 0;
- the schema command prints schema ok;
- git diff --check prints no errors;
- git status --short is empty after committing the implementation.

- [ ] Step 2: Verify the package file set

Run:

~~~powershell
rg --files -g '!__pycache__' -g '!*.pyc' | Sort-Object
~~~

Confirm the output contains main.py, metadata.yaml, _conf_schema.json, README.md, all mc_version_watcher/*.py modules, and all planned tests.

- [ ] Step 3: Perform the real AstrBot manual acceptance

Install or copy the plugin into an AstrBot instance, reload it, and verify in a real adapter session:

1. Send /mcversion umo in a private chat and in a group chat; confirm each returned string is copied unchanged into push_umos.
2. Save a configuration with the default release and snapshot types and at least one target UMO.
3. Reload the plugin and confirm the first successful check does not send historical versions.
4. As an administrator, send /mcversion test; confirm the configured target receives the visibly synthetic update and the invoking session receives the success/failure summary.
5. Send /mcversion latest; confirm release and snapshot appear as separate lines and an RC/pre entry receives its extra label when currently present.

Report this manual adapter check separately from the offline automated test results; a passing import test is not evidence that a real platform delivered a proactive message.

- [ ] Step 4: Create the final implementation commit only if verification-only adjustments were needed

~~~powershell
git status --short
git diff --check
git add .
git commit -m "test: verify Minecraft version watcher package"
~~~

Only make this commit when the preceding verification-only changes are real and reviewed; do not create an empty commit.
