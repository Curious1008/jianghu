#!/usr/bin/env python3
"""Pattern router for the 心魔 prompt.

Input: signals JSON (from _git_signals.py) on stdin or --signals FILE.
Output: {"pattern": "P1"|"P2"|"P3"|"P4"|"P5"|"silence", "reason": str, "evidence": {...}}

Routing per design (FROZEN 2026-05-07, section "Routing — Option α"):

    multi commit type + multi dir              → P1
    single dir + single dominant action         → P2
    multi dir + multi branch + scattered TODOs  → P3
    behavior categorizable + countable          → P4
    visible push activity + dark corner silent  → P5
    no significant signal                       → silence

Priority (most specific → least): P5 → P3 → P4 → P2 → P1 → silence.

Thresholds (tunable; live data will move these):
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

# Thresholds.
MIN_COMMITS = 5
MULTI_DIR = 2
MULTI_TYPE = 2
DOMINANT_RATIO = 0.6
DOMINANT_MIN_COMMITS = 5
CATEGORIZABLE_DIRS = 3
SCATTERED_TODOS = 5
ACTIVE_BRANCHES = 2
DARK_CORNER_README_AGE = 30


def _is_active_branch(b: dict) -> bool:
    return (not b.get("merged")) and b.get("ahead", 0) > 0


def _commits_in_top_dir(dirs: list[dict]) -> tuple[str, int, int]:
    """Returns (top_dir, top_count, total_count). All zero if no dirs."""
    if not dirs:
        return ("", 0, 0)
    total = sum(d.get("commits", 0) for d in dirs)
    top = dirs[0]
    return (top.get("dir", ""), top.get("commits", 0), total)


def route(sig: dict) -> dict:
    if not sig.get("is_git_repo") or sig.get("commits_in_window", 0) == 0:
        return {
            "pattern": "silence",
            "reason": "no commits in window or not a git repo",
            "evidence": {},
        }

    dirs = sig.get("dirs", []) or []
    commit_types = sig.get("commit_types", []) or []
    branches = sig.get("branches", []) or []
    todos = sig.get("todos", 0) or 0
    readme_age = sig.get("readme_age_days")
    total_commits = sig.get("commits_in_window", 0)

    active_branches = [b for b in branches if _is_active_branch(b)]
    n_dirs = len(dirs)
    n_types = len(commit_types)
    top_dir, top_count, _ = _commits_in_top_dir(dirs)
    has_dominance = (
        total_commits >= DOMINANT_MIN_COMMITS
        and top_count / max(1, total_commits) >= DOMINANT_RATIO
    )
    dark_corner = (
        readme_age is not None
        and readme_age >= DARK_CORNER_README_AGE
        and total_commits > 0
    )

    # P5 — surface activity + cold README. Most psychologically specific.
    if dark_corner and n_dirs >= 1:
        non_doc_dirs = [d for d in dirs if d["dir"] not in {"docs", "doc"}]
        surface = non_doc_dirs[0]["dir"] if non_doc_dirs else dirs[0]["dir"]
        return {
            "pattern": "P5",
            "reason": "active surface dir + README untouched",
            "evidence": {
                "surface_dir": surface,
                "surface_commits": dirs[0]["commits"],
                "readme_age_days": readme_age,
            },
        }

    # P3 — scattered across dirs + branches + TODOs.
    if (
        n_dirs >= CATEGORIZABLE_DIRS
        and len(active_branches) >= ACTIVE_BRANCHES
        and todos >= SCATTERED_TODOS
    ):
        return {
            "pattern": "P3",
            "reason": "scattered: multi-dir + multi-branch + many TODOs",
            "evidence": {
                "dirs": [d["dir"] for d in dirs[:5]],
                "active_branches": [b["name"] for b in active_branches],
                "todos": todos,
            },
        }

    # P4 — ≥3 dirs with countable activity (matrix-able).
    if n_dirs >= CATEGORIZABLE_DIRS:
        return {
            "pattern": "P4",
            "reason": "categorizable behavior across ≥3 dirs",
            "evidence": {
                "rows": [
                    {"dir": d["dir"], "commits": d["commits"]} for d in dirs[:5]
                ],
            },
        }

    # P2 — dominant single dir.
    if has_dominance:
        return {
            "pattern": "P2",
            "reason": "single-dir dominance",
            "evidence": {
                "dominant_dir": top_dir,
                "top_count": top_count,
                "total_commits": total_commits,
            },
        }

    # P1 — multi-dir + multi-type fallback.
    if n_dirs >= MULTI_DIR and n_types >= MULTI_TYPE:
        return {
            "pattern": "P1",
            "reason": "multi-dir + multi commit-type",
            "evidence": {
                "dirs": [d["dir"] for d in dirs[:4]],
                "types": commit_types,
            },
        }

    return {
        "pattern": "silence",
        "reason": "insufficient signal — clean week",
        "evidence": {
            "commits_in_window": total_commits,
            "n_dirs": n_dirs,
            "n_types": n_types,
        },
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--signals",
        help="path to signals JSON (default: read stdin)",
        default=None,
    )
    args = parser.parse_args(argv[1:])
    if args.signals:
        with open(args.signals, "r", encoding="utf-8") as f:
            sig = json.load(f)
    else:
        sig = json.load(sys.stdin)
    sys.stdout.write(json.dumps(route(sig), ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
