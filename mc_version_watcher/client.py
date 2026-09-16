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
