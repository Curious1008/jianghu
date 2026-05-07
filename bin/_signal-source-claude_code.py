#!/usr/bin/env python3
"""Cache-backed assistant-message counter for Claude Code jsonl logs.

Counts lines matching `"type":"assistant"` across `~/.claude/projects/*/*.jsonl`,
caching per-file (mtime, size, count) so warm calls only stat files instead of
re-reading them.

Contract:
    argv[1] (optional): since_iso. If non-empty, bypass cache and do a full
                        filtered scan counting only assistant lines whose
                        `timestamp` field is strictly greater than since_iso.
    argv[2] (optional): cache_path. Defaults to ~/.jianghu/.breath-cache.json.
    argv[3] (optional): projects_glob. Defaults to ~/.claude/projects/*/*.jsonl.
                        Tests inject fixture paths here.

stdout: a single integer (the count). Nothing else.
stderr: warnings (e.g. corrupt cache dropped).
"""
from __future__ import annotations

import glob
import json
import os
import sys
import tempfile

CACHE_VERSION = 1
ASSISTANT_MARKER = b'"type":"assistant"'


def count_assistant_lines(path: str) -> int:
    n = 0
    try:
        with open(path, "rb") as f:
            for line in f:
                if ASSISTANT_MARKER in line:
                    n += 1
    except OSError:
        return 0
    return n


def count_filtered(path: str, since_iso: str) -> int:
    n = 0
    try:
        with open(path, "rb") as f:
            for line in f:
                if ASSISTANT_MARKER not in line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                ts = rec.get("timestamp")
                if isinstance(ts, str) and ts > since_iso:
                    n += 1
    except OSError:
        return 0
    return n


def load_cache(cache_path: str) -> dict:
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("cache root not object")
        if data.get("version") != CACHE_VERSION:
            raise ValueError("cache version mismatch")
        files = data.get("files")
        if not isinstance(files, dict):
            raise ValueError("cache files not object")
        return data
    except FileNotFoundError:
        return {"version": CACHE_VERSION, "files": {}, "total": 0}
    except (OSError, ValueError) as e:
        sys.stderr.write(f"[jianghu] breath cache dropped: {e}\n")
        try:
            os.unlink(cache_path)
        except OSError:
            pass
        return {"version": CACHE_VERSION, "files": {}, "total": 0}


def atomic_write(cache_path: str, data: dict) -> None:
    parent = os.path.dirname(cache_path) or "."
    try:
        os.makedirs(parent, exist_ok=True)
    except OSError:
        return
    fd, tmp = tempfile.mkstemp(prefix=".breath-cache.", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
        os.replace(tmp, cache_path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def count_all(cache_path: str, projects_glob: str) -> int:
    paths = sorted(glob.glob(projects_glob))
    cache = load_cache(cache_path)
    files = cache["files"]
    new_files: dict[str, dict] = {}
    total = 0
    dirty = False

    for path in paths:
        try:
            st = os.stat(path)
        except OSError:
            continue
        mtime = st.st_mtime
        size = st.st_size
        entry = files.get(path)
        if (
            entry
            and entry.get("mtime") == mtime
            and entry.get("size_bytes") == size
            and isinstance(entry.get("count"), int)
        ):
            count = entry["count"]
        else:
            count = count_assistant_lines(path)
            dirty = True
        new_files[path] = {"mtime": mtime, "size_bytes": size, "count": count}
        total += count

    if set(new_files.keys()) != set(files.keys()):
        dirty = True

    if dirty or cache.get("total") != total:
        atomic_write(
            cache_path,
            {"version": CACHE_VERSION, "files": new_files, "total": total},
        )
    return total


def count_since(projects_glob: str, since_iso: str) -> int:
    total = 0
    for path in sorted(glob.glob(projects_glob)):
        total += count_filtered(path, since_iso)
    return total


def main(argv: list[str]) -> int:
    since_iso = argv[1] if len(argv) > 1 else ""
    home = os.path.expanduser("~")
    default_cache = os.path.join(home, ".jianghu", ".breath-cache.json")
    default_glob = os.path.join(home, ".claude", "projects", "*", "*.jsonl")
    cache_path = argv[2] if len(argv) > 2 and argv[2] else default_cache
    projects_glob = argv[3] if len(argv) > 3 and argv[3] else default_glob

    if since_iso:
        n = count_since(projects_glob, since_iso)
    else:
        n = count_all(cache_path, projects_glob)
    sys.stdout.write(f"{n}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
