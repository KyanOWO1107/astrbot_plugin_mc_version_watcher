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
