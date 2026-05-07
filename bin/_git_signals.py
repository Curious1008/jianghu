#!/usr/bin/env python3
"""Git signal extractor for /jianghu daily ritual.

Reads the git repo at $CWD (or --repo PATH) and emits a JSON object that the
pattern router and prompt builder consume. All counts are 7-day windows by
default (window adjustable via --days).

The extractor never invokes an LLM and never mutates the repo. It treats all
errors (no git, detached HEAD, no commits, missing README, etc.) as soft —
unknown fields are emitted as null/[]/0 so downstream code can cleanly route
to the silence fallback.

Usage:
    _git_signals.py [--repo PATH] [--days N]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone


CONVENTIONAL_PREFIXES = {
    "feat",
    "fix",
    "refactor",
    "chore",
    "docs",
    "test",
    "style",
    "perf",
    "build",
    "ci",
    "revert",
}


def run_git(repo: str, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", repo, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout if out.returncode == 0 else ""


def is_git_repo(repo: str) -> bool:
    return run_git(repo, "rev-parse", "--git-dir").strip() != ""


def top_level_dir(path: str) -> str:
    """`auth/middleware/clerk.ts` → `auth`. Files at root → `.`."""
    parts = path.split("/", 1)
    return parts[0] if len(parts) > 1 else "."


def extract_commit_type(subject: str) -> str | None:
    m = re.match(r"^([a-z]+)(?:\([^)]+\))?[!:]?\s*:", subject.lower())
    if m and m.group(1) in CONVENTIONAL_PREFIXES:
        return m.group(1)
    return None


def collect_window_commits(repo: str, days: int) -> list[dict]:
    """Returns [{sha, ts, subject, dirs, type}] for commits in the last N days."""
    raw = run_git(
        repo,
        "log",
        f"--since={days}.days.ago",
        "--no-merges",
        "--pretty=format:%H%x09%cI%x09%s",
        "--name-only",
    )
    commits: list[dict] = []
    if not raw:
        return commits

    blocks = raw.split("\n\n")
    for block in blocks:
        lines = [ln for ln in block.split("\n") if ln]
        if not lines:
            continue
        head = lines[0].split("\t", 2)
        if len(head) < 3:
            continue
        sha, ts, subject = head
        files = lines[1:]
        dirs = sorted({top_level_dir(f) for f in files if f})
        commits.append(
            {
                "sha": sha,
                "ts": ts,
                "subject": subject,
                "dirs": dirs,
                "type": extract_commit_type(subject),
            }
        )
    return commits


def collect_branch_state(repo: str) -> list[dict]:
    """Local branches with main-branch divergence + age."""
    main = detect_main_branch(repo)
    raw = run_git(repo, "branch", "--format=%(refname:short)")
    branches: list[dict] = []
    for name in raw.strip().split("\n"):
        name = name.strip()
        if not name or name == main:
            continue
        ahead = run_git(repo, "rev-list", "--count", f"{main}..{name}").strip()
        merged = run_git(repo, "branch", "--merged", main).strip()
        is_merged = any(
            ln.strip().lstrip("* ").strip() == name for ln in merged.split("\n")
        )
        last_ts = run_git(repo, "log", "-1", "--pretty=format:%cI", name).strip()
        age_days = age_days_from_iso(last_ts)
        branches.append(
            {
                "name": name,
                "ahead": int(ahead) if ahead.isdigit() else 0,
                "merged": is_merged,
                "age_days": age_days,
            }
        )
    return branches


def detect_main_branch(repo: str) -> str:
    for candidate in ("main", "master"):
        if run_git(repo, "rev-parse", "--verify", candidate).strip():
            return candidate
    head = run_git(repo, "symbolic-ref", "HEAD").strip()
    return head.rsplit("/", 1)[-1] if head else "main"


def age_days_from_iso(iso: str) -> int | None:
    if not iso:
        return None
    try:
        ts = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - ts
    return max(0, int(delta.total_seconds() // 86400))


def push_lag(repo: str, main: str) -> int | None:
    """Commits on local main not on origin/main. None if no remote."""
    origin = run_git(repo, "rev-parse", "--verify", f"origin/{main}").strip()
    if not origin:
        return None
    out = run_git(repo, "rev-list", "--count", f"origin/{main}..{main}").strip()
    return int(out) if out.isdigit() else 0


def todo_count(repo: str) -> int:
    raw = run_git(repo, "grep", "-I", "-E", "-c", r"TODO|FIXME|XXX")
    if not raw:
        return 0
    n = 0
    for line in raw.strip().split("\n"):
        if ":" not in line:
            continue
        try:
            n += int(line.rsplit(":", 1)[1])
        except ValueError:
            continue
    return n


def readme_age_days(repo: str) -> int | None:
    for name in ("README.md", "README.MD", "README", "readme.md"):
        path = os.path.join(repo, name)
        if not os.path.exists(path):
            continue
        ts = run_git(repo, "log", "-1", "--pretty=format:%cI", "--", name).strip()
        if ts:
            return age_days_from_iso(ts)
        # Fall back to filesystem mtime if file is untracked.
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return None
        delta = datetime.now(timezone.utc).timestamp() - mtime
        return max(0, int(delta // 86400))
    return None


def collect_dir_activity(commits: list[dict]) -> list[dict]:
    counter: Counter[str] = Counter()
    last_seen: dict[str, str] = {}
    for c in commits:
        for d in c["dirs"]:
            counter[d] += 1
            if d not in last_seen or c["ts"] > last_seen[d]:
                last_seen[d] = c["ts"]
    out: list[dict] = []
    for d, n in counter.most_common():
        out.append(
            {"dir": d, "commits": n, "last_age_days": age_days_from_iso(last_seen[d])}
        )
    return out


def messages_for_daoxin(repo: str) -> dict:
    """Recent commits + an old meaningful message (≥50 chars body / not boilerplate)."""
    recent_raw = run_git(repo, "log", "-5", "--pretty=format:%s")
    recent = [ln for ln in recent_raw.strip().split("\n") if ln]
    old_raw = run_git(
        repo,
        "log",
        "--reverse",
        "--pretty=format:%cI%x09%s",
    )
    old_msg: str | None = None
    old_ts: str | None = None
    for line in old_raw.strip().split("\n"):
        if "\t" not in line:
            continue
        ts, subject = line.split("\t", 1)
        if len(subject) >= 50 and not subject.lower().startswith(
            ("merge ", "initial commit", "init")
        ):
            old_msg = subject
            old_ts = ts
            break
    return {
        "recent_subjects": recent,
        "oldest_meaningful": (
            {"ts": old_ts, "subject": old_msg, "age_days": age_days_from_iso(old_ts)}
            if old_msg
            else None
        ),
    }


def build_signals(repo: str, days: int) -> dict:
    if not is_git_repo(repo):
        return {
            "repo": repo,
            "is_git_repo": False,
            "window_days": days,
            "commits_in_window": 0,
            "dirs": [],
            "branches": [],
            "commit_types": [],
            "todos": 0,
            "readme_age_days": None,
            "push_lag": None,
            "messages": {"recent_subjects": [], "oldest_meaningful": None},
        }

    main = detect_main_branch(repo)
    commits = collect_window_commits(repo, days)
    dirs = collect_dir_activity(commits)
    branches = collect_branch_state(repo)
    types = sorted({c["type"] for c in commits if c["type"]})
    return {
        "repo": repo,
        "is_git_repo": True,
        "window_days": days,
        "main_branch": main,
        "commits_in_window": len(commits),
        "dirs": dirs,
        "branches": branches,
        "commit_types": types,
        "todos": todo_count(repo),
        "readme_age_days": readme_age_days(repo),
        "push_lag": push_lag(repo, main),
        "messages": messages_for_daoxin(repo),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.getcwd())
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args(argv[1:])
    sig = build_signals(args.repo, args.days)
    sys.stdout.write(json.dumps(sig, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
