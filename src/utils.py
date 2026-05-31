"""
Utilities module — shared helpers, logging, and integrity tooling.

Responsibilities (Phase 3+):
- JSON logging setup: configure Python's logging module with a JSON formatter
  emitting {timestamp, level, module, message} records to a rotating log file
  in logs/ (excluded from git via .gitignore) and to stdout.
- compute_sha256(filepath): compute and return the SHA256 hash of any file.
  Used by process_videos.py to fingerprint each input video and write
  video_hashes.json alongside events.json.
- load_config(path="config.json"): load and return config.json as a dict.
  Raise a clear error if required keys are missing.
- load_zones(path="zones.json"): load and return zones.json as a dict.
  Warn (do not crash) if any polygon or entry_line is still empty (TODO state),
  so the pipeline can partially run during development.
- format_duration(seconds): convert raw seconds to human-readable string
  (e.g., "2h 14m 32s") for display in README and System Health tab.
- In-memory log buffer: maintain a deque of the last 50 log entries,
  accessible by api.py for the /health endpoint System Health response.
"""
