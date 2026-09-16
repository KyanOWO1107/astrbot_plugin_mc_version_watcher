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
