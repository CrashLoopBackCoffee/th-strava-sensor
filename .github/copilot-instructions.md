## GitHub Copilot Project Instructions (Strava Sensor)

Purpose: Help AI agents make fast, correct changes in this repo by understanding architecture, workflows, and conventions. Keep responses concrete, reflect current code, and prefer existing patterns over reinvention.

### 1. Core Mission
Parse cycling/running activity FIT files (from file system, Garmin Connect, or via Strava indirection), extract device battery telemetry, optionally publish device statuses and Home Assistant MQTT discovery payloads.

### 2. High-Level Flow
parse-activity CLI -> source selection (file / garmin / strava delegation) -> fetch FIT bytes -> FitFile parse & validation -> build DeviceStatus models -> optional MQTT publish (status + HA discovery) -> log & exit (or keep process alive for MQTT).

### 2a. Terminal Initialization
Always start a fresh terminal session with a harmless command first to ensure environment (venv activation, path resolution) is stable before heavier commands:
`echo "init"`
Then run dependency sync or checks (e.g., `uv sync`, pre-commit hooks). This avoids first-command slowdown impacting meaningful operations.

### 2b. Git Workflow (Lightweight)
- Never commit directly to `main`; use feature branches (`feat/`, `fix/`, `docs/`).
- Keep PRs focused (single concern) and reference sections of this file in descriptions.
- Run `uv sync` after editing `pyproject.toml` before tests/linters.

### 3. Key Modules
- `src/strava_sensor/cli.py`: Entry point, source initialization order matters: File -> (conditional Garmin) -> (conditional Strava; needs downstream list). Adds Strava only if `STRAVA_REFRESH_TOKEN` is set. MQTT only if `--publish` and all MQTT env vars.
- `source/base.py`: Matching logic via URI scheme or HTTP hosts; extend by subclassing `BaseSource` and implementing `read_activity` (+ optional `find_activity`).
- `source/garmin.py`: Auth via `garminconnect`; token caching path from `GARMINTOKENS` or `~/.garminconnect`. `find_activity` fuzzy matches (±60s time, ±100m distance). Returns `garmin://<id>` URIs.
- `source/strava.py`: Cannot download FIT directly; uses Strava API for metadata then delegates to downstream sources by calling their `find_activity` and `read_activity`.
- `fitfile/fitfile.py`: Wraps Garmin FIT SDK. Validates required message presence & type. Raises typed errors (`NotAFitFileError`, `CorruptedFitFileError`, `InvalidActivityFileError`). Extracts devices from `device_info_mesgs` only when `battery_status` present.
- `fitfile/model.py`: `DeviceStatus` (Pydantic v2) with post-validators applying manufacturer & source-specific overrides (`MODEL_OVERRIDE`). Publishes MQTT status + HA discovery bundle in one go.
- `mqtt/mqtt.py` (not shown above if editing elsewhere): Thin wrapper expected to expose `connect`, `publish`, `disconnect`, and `connected` flag.

### 4. Conventions & Patterns
- Environment-driven feature enabling (Garmin & Strava sources, MQTT publishing). Never crash just because optional envs are absent—mirror existing guards.
- URI routing: Always prefer `matches_uri` instead of manual parsing duplication.
- Strava delegation: Maintain downstream list order; do not mutate after construction.
- Validation: Prefer raising existing custom exceptions from `fitfile.py` for parse failures.
- Logging: Use module-level `_logger`; respect existing debug/info levels (daiquiri configured in `setup_logging`).
- Pydantic models: Allow extras; strip non-string keys before model validation (see `get_devices_status`). Follow that if creating new models fed by FIT raw messages.
- Manufacturer overrides: Extend `MODEL_OVERRIDE` rather than hardcoding mapping logic in other places.
- Home Assistant discovery: Retain topic structure: `homeassistant/device/strava-<serial>/config` and state topic `strava/<serial_number>/status`.

### 5. Adding a New Source (Example Checklist)
1. Create `source/<name>.py`, subclass `BaseSource`.
2. Define `uri_scheme` and/or `http_hosts`.
3. Implement `read_activity` returning raw FIT bytes (zip decode if needed).
4. (Optional) Implement `find_activity` with fuzzy matching analogous to Garmin if supporting Strava delegation.
5. Wire into `initialize_sources()` in `cli.py` maintaining ordering (non-delegating sources before Strava).

### 6. Adding Device Overrides
Edit `MODEL_OVERRIDE` in `fitfile/model.py`: nested dict keyed by lowercase manufacturer -> product code -> friendly name. Keep keys as strings. Do not alter validator logic.

### 7. Tests & Quality
- Always run `uv run ./scripts/run-all-checks.sh` before committing (aggregates pre-commit hooks + tests). Re-run if it auto-fixes.
- Let pre-commit auto-fix first; only hand-edit style issues if still failing after a second run.
- Full suite: `uv run pre-commit run --all-files --show-diff-on-failure`. Direct tests: `uv run pytest -v`.
- Keep FIT fixtures minimal in `tests/fixtures/`.
- Respect Ruff config (line-length 100, single quotes). Avoid churn for ignored rules.

### 8. Error Handling Expectations
- Prefer explicit error handling over silent failures.
- Log errors with sufficient context for diagnosis.
- Provide fallback mechanisms where recovery is possible.

### 9. MQTT Publishing Behavior
- Publish device status updates at regular intervals or upon state change.
- Ensure MQTT connection is stable before publishing.
- Handle MQTT disconnections gracefully, with retries as configured.

### 10. Safe Refactors
- Favor small, incremental changes with clear, testable outcomes.
- Ensure comprehensive test coverage before refactoring.
- Use feature flags to toggle new behavior without impacting all users.

### 11. Common Pitfalls
- Ignoring existing code patterns and conventions.
- Making large, untested changes directly in `main`.
- Forgetting to update documentation or instructions alongside code changes.

### 12. Interactive Feedback Protocol
- Whenever you want to ask a question, always call the MCP interactive.
- Whenever you're about to complete a user request, call the MCP interactive instead of simply ending the process.
- Keep calling MCP until the user's feedback is empty, then end the request.
- This ensures interactive, user-driven completion and review of all Copilot actions.

### 13. When Unsure
- Consult this document or existing code patterns.
- Break down the problem and tackle it incrementally.
- Seek clarification or assistance if the path forward is unclear, call the MCP interactive in this case.

---
Provide PR descriptions that cite which section (e.g., "Adds new Source per Section 5 checklist") to speed AI and human review.
