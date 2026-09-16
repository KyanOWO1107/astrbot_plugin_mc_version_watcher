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
