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
