# Minecraft Version Watcher Design

**Date:** 2026-09-15  
**Status:** Approved for implementation planning

## Goal

Build an AstrBot plugin that periodically checks Mojang's official Minecraft version manifest, reports the latest enabled version categories on demand, and pushes newly discovered versions to configured private or group chat sessions identified by UMO.

## Scope

The first version includes:

- A configurable asynchronous polling loop, defaulting to every 5 minutes.
- Monitoring of the official manifest's `release` and `snapshot` types.
- Extra display labels for `-pre` and `-rc` snapshot identifiers.
- A configurable list of private or group UMO targets.
- Persistent first-check baselines so existing versions are not announced on first startup.
- `/mcversion latest`, `/mcversion umo`, and administrator-only `/mcversion test` commands.
- Focused unit tests with an injectable fake manifest client and fake message sender.

The first version does not download version JSON files, inspect server compatibility, manage subscriptions through chat commands, or provide a web UI for editing targets.

## Product behavior

### Configuration

The plugin configuration schema exposes:

```json
{
  "check_interval_minutes": 5,
  "enabled_version_types": ["release", "snapshot"],
  "push_umos": []
}
```

- `check_interval_minutes` is an integer interval in minutes. Values below 1 are normalized to 1.
- `enabled_version_types` accepts `release` and `snapshot`. Its default enables both. Release candidates and pre-releases are not separate configuration types because Mojang classifies them as `snapshot`.
- `push_umos` is a string array. Empty strings are ignored and duplicate UMO values are removed while preserving their first-seen order.
- An empty `enabled_version_types` array disables monitoring but keeps the query commands available.
- An empty `push_umos` array disables proactive delivery but does not disable polling or local state updates.

### Version classification

The official manifest `type` field is authoritative:

- `release` is displayed as `Release（正式版）`.
- `snapshot` with an identifier matching `-rc` followed by an optional hyphen and number is displayed as `Snapshot（Release Candidate）`.
- `snapshot` with an identifier matching `-pre` followed by an optional hyphen and number is displayed as `Snapshot（Pre-release）`.
- Other `snapshot` identifiers are displayed as `Snapshot（普通快照）`.

The classifier supports both forms used by official identifiers, such as `1.21.11-rc3`, `26.3-rc-3`, `1.21.11-pre5`, and `26.3-pre-3`.

### Commands

`/mcversion latest` fetches the current official manifest and displays the newest matching version for each enabled type. It reports release and snapshot independently rather than selecting one global version. Snapshot labels include the pre-release or release-candidate annotation when applicable.

`/mcversion umo` returns `event.unified_msg_origin` exactly as the current session's UMO, so it can be copied into `push_umos`.

`/mcversion test` is restricted to AstrBot administrators. It creates a synthetic version object, formats it through the same formatter used for real updates, and sends the resulting message through the same `context.send_message(umo, MessageChain([Plain(...)]))` path to every configured UMO. The synthetic version is visibly marked as a test message, does not call Mojang, and does not modify the version state. The command's invoking session receives a summary of successful and failed target sends. With no configured targets, it reports that no push target is configured.

An invocation without a recognized subcommand returns concise usage text. Query commands are available to non-administrators; only the test push is privileged.

### Push message

Each polling cycle with one or more newly discovered versions sends one combined message per configured UMO. The message contains the version ID, official type, derived label, release time when present, and the official manifest source URL. Multiple new versions are listed in the manifest's order.

Example:

```text
Minecraft 版本更新

- 版本：26.3
  分类：Release（正式版）
  发布时间：2026-...

- 版本：26.3-rc-3
  分类：Snapshot（Release Candidate）
  发布时间：2026-...

来源：Mojang 官方版本清单
```

## Architecture

The implementation is split into small modules:

- `main.py` owns AstrBot registration, configuration normalization, lifecycle methods, commands, and calls into the service.
- `mc_version_watcher/models.py` contains immutable version and manifest data models plus the supported type constants.
- `mc_version_watcher/client.py` fetches and validates the official manifest. It uses the Python standard library HTTP client through `asyncio.to_thread`, a bounded request timeout, and no additional runtime dependency.
- `mc_version_watcher/service.py` filters versions, derives display labels, calculates new IDs against persisted state, formats update batches, and coordinates message delivery through an injected sender.
- `mc_version_watcher/state.py` loads and atomically saves the plugin's JSON state under `StarTools.get_data_dir("astrbot_plugin_mc_version_watcher")`.
- `mc_version_watcher/formatters.py` formats latest results, update batches, usage text, UMO output, and test summaries without depending on AstrBot internals.

The module names are a design boundary rather than a requirement to create unnecessary abstractions. Each module should keep only the interfaces required by the tests and `main.py`.

## Polling and baseline algorithm

1. `initialize()` loads the state and creates one cancellable background task for the polling loop.
2. The loop checks immediately, then waits for the configured interval before the next check.
3. A check fetches and validates the manifest before touching state.
4. It filters the `versions` list by the enabled official types and keeps the manifest order.
5. For each enabled type without an initialized baseline, it records all currently visible IDs and emits no notification.
6. For an initialized type, it computes `current_ids - seen_ids`, formats new entries, and sends at most one combined update message to each target.
7. After a valid check and delivery attempts, it persists the current IDs atomically. A failed target is logged and does not block other targets; v1 advances global state after the attempt to prevent successful targets from receiving duplicate notifications on every subsequent cycle.
8. A disabled type keeps its prior state. If it is enabled again later, only versions not already recorded are eligible for notification.
9. `terminate()` cancels the polling task and awaits it, suppressing the expected cancellation exception.

The state format is versioned for future migrations:

```json
{
  "schema_version": 1,
  "initialized_types": ["release", "snapshot"],
  "seen_versions": {
    "release": ["26.3"],
    "snapshot": ["26.3-rc-3", "26w14a"]
  }
}
```

The state writer writes a temporary file in the same directory and replaces the destination, preventing a partially written JSON file during shutdown. A malformed or incompatible state file is logged and treated as empty state, which safely causes a new baseline instead of historical notifications.

## Error handling

- HTTP timeout, network failure, non-success status, invalid JSON, or a manifest missing required `id`/`type` fields causes the current check to fail without changing state. The loop logs the failure and retries at the next interval.
- Missing optional release-time data does not invalidate an otherwise valid version; the formatter omits that line.
- A send failure for one UMO is isolated, logged with the target value, and included in the administrator-facing test summary. It does not prevent sends to other targets.
- `/mcversion latest` reports a user-readable fetch failure and never falls back to stale data without explicitly saying so.
- Invalid configured type values are ignored. If no valid types remain, monitoring is disabled until configuration changes.

## Testing strategy

Tests will be separated by responsibility:

- Model/client tests validate manifest parsing, required fields, official type filtering, release-time handling, and `rc`/`pre` label detection using in-memory fixtures.
- State tests validate missing-state initialization, malformed-state recovery, deduplication, and atomic-save behavior through a temporary directory.
- Service tests validate first-check no-notify behavior, new-version detection, disabled-type filtering, combined batch formatting, target isolation, and no state mutation for the synthetic test push.
- Command tests load `main.py` with small AstrBot stubs, verifying `latest`, `umo`, administrator gating, and the real simulated send path.
- Lifecycle tests verify that initialization creates one polling task and termination cancels it without leaving a pending task.

Automated tests do not depend on the live Mojang endpoint. Manual acceptance in an AstrBot instance is required for `/mcversion umo`, configuring a real UMO, and `/mcversion test`; this confirms the platform adapter can receive proactive messages.

## Acceptance criteria

The feature is complete when:

1. A fresh plugin installation can load with the default release and snapshot configuration.
2. The first successful check records current versions without sending historical notifications.
3. A later manifest containing a new release or snapshot produces one formatted push per configured UMO.
4. `-rc` and `-pre` entries remain selectable through `snapshot` and are visibly annotated.
5. `/mcversion latest` returns separate enabled-category results, and `/mcversion umo` returns the exact current UMO.
6. Administrator `/mcversion test` sends a visibly synthetic version message through the actual configured targets without changing state.
7. Network failures, malformed state, and individual target failures are handled without crashing the background task.
8. Focused tests and the full test suite pass, and the final package contains the plugin metadata and configuration schema required by AstrBot.
