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
