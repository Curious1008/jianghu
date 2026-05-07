#!/usr/bin/env python3
"""config.json manager for /jianghu.

Same single-writer + atomic-rename pattern as _state.py. Corrupt config →
quarantine + restore defaults (silent recovery, less weight than state).

Usage:
    _config.py init                ensure config.json exists with defaults
    _config.py read                print full config JSON
    _config.py get <field>         print one field as JSON
    _config.py set <field> <json>  merge field, atomic-write

Env: JIANGHU_HOME (default ~/.jianghu)
"""
from __future__ import annotations

import json
import os
import signal
import sys
import tempfile
import time
from datetime import datetime, timezone

DEFAULTS = {
    "enabled_sources": ["claude_code"],
    "chrome_theme": "off",
    "frame_style": "rich",
    "effects": "on",
}


def home_dir() -> str:
    return os.environ.get("JIANGHU_HOME") or os.path.join(
        os.path.expanduser("~"), ".jianghu"
    )


def config_path() -> str:
    return os.path.join(home_dir(), "config.json")


def quarantine_corrupt(path: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dst = f"{path}.corrupt-{ts}"
    try:
        os.replace(path, dst)
    except OSError:
        return ""
    return dst


def load_config() -> dict:
    p = config_path()
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("config root not object")
        merged = dict(DEFAULTS)
        merged.update(data)
        return merged
    except FileNotFoundError:
        return dict(DEFAULTS)
    except (OSError, ValueError) as e:
        sys.stderr.write(f"[jianghu] config.json corrupt, restoring defaults: {e}\n")
        quarantine_corrupt(p)
        return dict(DEFAULTS)


def atomic_write(data: dict) -> None:
    p = config_path()
    parent = os.path.dirname(p) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".config.", dir=parent)

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


def cmd_init(_argv: list[str]) -> int:
    if not os.path.exists(config_path()):
        atomic_write(dict(DEFAULTS))
    else:
        # Validate; if corrupt, load_config quarantines and we re-write defaults.
        cfg = load_config()
        if not os.path.exists(config_path()):
            atomic_write(cfg)
    return 0


def cmd_read(_argv: list[str]) -> int:
    sys.stdout.write(json.dumps(load_config(), ensure_ascii=False, indent=2) + "\n")
    return 0


def cmd_get(argv: list[str]) -> int:
    if not argv:
        sys.stderr.write("get requires <field>\n")
        return 1
    cfg = load_config()
    if argv[0] not in cfg:
        sys.stderr.write(f"unknown field: {argv[0]}\n")
        return 1
    sys.stdout.write(json.dumps(cfg[argv[0]], ensure_ascii=False) + "\n")
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
    cfg = load_config()
    cfg[field] = value
    atomic_write(cfg)
    return 0


COMMANDS = {"init": cmd_init, "read": cmd_read, "get": cmd_get, "set": cmd_set}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in COMMANDS:
        sys.stderr.write("usage: _config.py {init|read|get FIELD|set FIELD VALUE}\n")
        return 1
    return COMMANDS[argv[1]](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
