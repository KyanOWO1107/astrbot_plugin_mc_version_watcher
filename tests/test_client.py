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
