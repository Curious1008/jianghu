#!/usr/bin/env python3
"""state.json manager for /jianghu.

Single writer (per Sync Architecture). Atomic write via tmp + os.replace.
F2 recovery: corrupt state.json is moved aside and replaced with defaults.

Usage:
    _state.py init  [--breath N]   write defaults if state.json absent
    _state.py read                  print full state JSON
    _state.py get <field>           print one field as JSON
    _state.py set <field> <json>    merge field, atomic-write

Env:
    JIANGHU_HOME            override ~/.jianghu
    JIANGHU_TEST_WRITE_DELAY  seconds to sleep between tmp-write and rename
                              (test-only; defaults to 0)

Exit codes:
    0  ok
    1  bad usage / unknown field on `get`
"""
from __future__ import annotations

import json
import os
import signal
import sys
import tempfile
import time
from datetime import datetime, timezone

SCHEMA_VERSION = 1


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_state(breath: int = 0) -> dict:
    ts = now_iso()
    return {
        "schema_version": SCHEMA_VERSION,
        "journey_started_at": ts,
        "journey_started_breath": breath,
        "current_realm": "凡",
        "realm_index": 0,
        "realm_entered_at": ts,
        "realm_entered_breath": breath,
        "daoxin_name": None,
        "daoxin_name_en": None,
        "ritual_count": 0,
        "last_ritual_at": None,
        "in_seclusion": False,
        "seclusion_started_at": None,
        "seclusion_target_realm": None,
        "seclusion_answers": [],
        "first_run_complete": False,
        "first_run_at": None,
        "first_run_breath": None,
        "first_run_realm": None,
        "last_harry_prompt_at": None,
    }


def home_dir() -> str:
    return os.environ.get("JIANGHU_HOME") or os.path.join(
        os.path.expanduser("~"), ".jianghu"
    )


def state_path() -> str:
    return os.path.join(home_dir(), "state.json")


def quarantine_corrupt(path: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dst = f"{path}.corrupt-{ts}"
    try:
        os.replace(path, dst)
    except OSError:
        return ""
    return dst


def load_state() -> tuple[dict, bool]:
    """Return (state, recovered). recovered=True means F2 path was hit."""
    p = state_path()
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("state root not object")
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(
                f"schema_version mismatch (got {data.get('schema_version')})"
            )
        # Backfill any keys added since this state was written.
        merged = default_state()
        merged.update(data)
        merged["schema_version"] = SCHEMA_VERSION
        return merged, False
    except FileNotFoundError:
        return default_state(), False
    except (OSError, ValueError) as e:
        sys.stderr.write(f"[jianghu] state.json corrupt, rebuilding: {e}\n")
        quarantine_corrupt(p)
        return default_state(), True


def atomic_write(data: dict) -> None:
    p = state_path()
    parent = os.path.dirname(p) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".state.", dir=parent)

    def _on_term(_signum, _frame):
        try:
            os.unlink(tmp)
        except OSError:
            pass
        os._exit(143)

    old_term = signal.signal(signal.SIGTERM, _on_term)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        delay = float(os.environ.get("JIANGHU_TEST_WRITE_DELAY", "0") or 0)
        if delay > 0:
            time.sleep(delay)
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    finally:
        signal.signal(signal.SIGTERM, old_term)


def cmd_init(argv: list[str]) -> int:
    breath = 0
    if "--breath" in argv:
        i = argv.index("--breath")
        if i + 1 < len(argv):
            try:
                breath = int(argv[i + 1])
            except ValueError:
                sys.stderr.write("--breath requires integer\n")
                return 1
    p = state_path()
    if os.path.exists(p):
        # Don't overwrite. Still validate; if corrupt, F2 recovers.
        state, _ = load_state()
        # If F2 recovered, we now have defaults in memory but file is gone —
        # write defaults out (with breath if given).
        if not os.path.exists(p):
            atomic_write(default_state(breath))
        return 0
    atomic_write(default_state(breath))
    return 0


def cmd_read(_argv: list[str]) -> int:
    state, _ = load_state()
    sys.stdout.write(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    return 0


def cmd_get(argv: list[str]) -> int:
    if not argv:
        sys.stderr.write("get requires <field>\n")
        return 1
    field = argv[0]
    state, _ = load_state()
    if field not in state:
        sys.stderr.write(f"unknown field: {field}\n")
        return 1
    sys.stdout.write(json.dumps(state[field], ensure_ascii=False) + "\n")
    return 0


def cmd_set(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.stderr.write("set requires <field> <json-value>\n")
        return 1
    field, raw = argv[0], argv[1]
    try:
        value = json.loads(raw)
    except ValueError as e:
        sys.stderr.write(f"invalid json value: {e}\n")
        return 1
    state, _ = load_state()
    state[field] = value
    atomic_write(state)
    return 0


COMMANDS = {
    "init": cmd_init,
    "read": cmd_read,
    "get": cmd_get,
    "set": cmd_set,
}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in COMMANDS:
        sys.stderr.write(
            "usage: _state.py {init [--breath N]|read|get FIELD|set FIELD VALUE}\n"
        )
        return 1
    return COMMANDS[argv[1]](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
