#!/usr/bin/env python3
"""Render the 观 (OBSERVED) section — bilingual deterministic facts.

Drawn from signals only. No interpretation. Two short paragraphs, ZH first.

Input:  --signals PATH  signals JSON
Output: {"zh": [str, ...], "en": [str, ...]}  (list of lines)
"""
from __future__ import annotations

import argparse
import json
import sys


def _zh_dirs(dirs: list[dict]) -> str:
    if not dirs:
        return "目下无动."
    parts = [f"{d['dir']}/ {d['commits']} 次" for d in dirs[:2]]
    return "皆在 " + ", ".join(parts) + "."


def _en_dirs(dirs: list[dict]) -> str:
    if not dirs:
        return "Nothing moved."
    parts = [f"{d['dir']}/ ×{d['commits']}" for d in dirs[:2]]
    return "All in " + ", ".join(parts) + "."


def render(sig: dict) -> dict:
    days = sig.get("window_days", 7)
    n = sig.get("commits_in_window", 0)
    dirs = sig.get("dirs", []) or []
    push_lag = sig.get("push_lag")
    readme_age = sig.get("readme_age_days")

    zh: list[str] = []
    en: list[str] = []

    if not sig.get("is_git_repo", False):
        zh.append("此处无山, 无江湖. 老道望气, 未见 git.")
        en.append("No mountain, no jianghu here. The hermit sees no git.")
        return {"zh": zh, "en": en}

    zh.append(f"过去 {days} 日 commit {n} 次.")
    en.append(f"{n} commits in {days} days.")
    zh.append(_zh_dirs(dirs))
    en.append(_en_dirs(dirs))

    if push_lag is not None:
        if push_lag == 0:
            zh.append("push 已至天涯.")
            en.append("Push is up to date.")
        else:
            zh.append(f"main 落后远端 {push_lag} 步.")
            en.append(f"Local main is {push_lag} commits behind origin.")
    elif n > 0:
        zh.append("未推. 江湖未见.")
        en.append("Not pushed. The world has not seen.")

    if readme_age is None:
        pass  # no README — silent
    elif readme_age >= 30:
        zh.append(f"README {readme_age} 日未触.")
        en.append(f"README untouched for {readme_age} days.")
    elif readme_age <= 1:
        zh.append("README 新写.")
        en.append("README freshly written.")

    return {"zh": zh, "en": en}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signals", required=True)
    args = parser.parse_args(argv[1:])
    with open(args.signals, "r", encoding="utf-8") as f:
        sig = json.load(f)
    sys.stdout.write(json.dumps(render(sig), ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
