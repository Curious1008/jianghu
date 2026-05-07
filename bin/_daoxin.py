#!/usr/bin/env python3
"""Deterministic 道心 (your daoxin holds) renderer.

Per design (line 360), encouragement uses ACTUAL content from user's history
(old commit messages). Never generic. Bilingual.

We pick the `oldest_meaningful` commit subject from signals (≥50 chars, not
boilerplate). If none exists, fall back to the most recent subject. If the
repo has zero commits, render the bare 道心未泯 closing.

Output: {"zh": str, "en": str, "quote": str|null, "age_days": int|null}
"""
from __future__ import annotations

import argparse
import json
import sys


def age_phrase_zh(days: int) -> str:
    if days < 3:
        return "前两日你写过"
    if days < 7:
        return "几日前你写过"
    if days < 30:
        weeks = max(1, days // 7)
        return f"{weeks} 周前你写过"
    if days < 60:
        return "一月前你写过"
    if days < 90:
        return "两月前你写过"
    if days < 180:
        months = days // 30
        return f"{months} 月前你写过"
    if days < 365:
        return "半年前你写过"
    years = days // 365
    if years == 1:
        return "去年你写过"
    return f"{years} 年前你写过"


def age_phrase_en(days: int) -> str:
    if days < 3:
        return "Two days back you wrote"
    if days < 7:
        return "A few days ago you wrote"
    if days < 30:
        weeks = max(1, days // 7)
        unit = "week" if weeks == 1 else "weeks"
        return f"{weeks} {unit} ago you wrote"
    if days < 60:
        return "A month ago you wrote"
    if days < 90:
        return "Two months ago you wrote"
    if days < 180:
        months = days // 30
        unit = "month" if months == 1 else "months"
        return f"{months} {unit} ago you wrote"
    if days < 365:
        return "Half a year ago you wrote"
    years = days // 365
    return ("Last year you wrote" if years == 1 else f"{years} years ago you wrote")


def render(sig: dict) -> dict:
    msgs = sig.get("messages", {}) or {}
    old = msgs.get("oldest_meaningful")
    if old and old.get("subject"):
        subject = old["subject"]
        age = old.get("age_days") or 0
        return {
            "quote": subject,
            "age_days": age,
            "zh": (
                f"{age_phrase_zh(age)}:\n"
                f'  "{subject}"\n'
                "道心未泯."
            ),
            "en": (
                f"{age_phrase_en(age)}:\n"
                f'  "{subject}"\n'
                "Your daoxin holds."
            ),
        }
    recent = msgs.get("recent_subjects") or []
    if recent:
        subject = recent[0]
        return {
            "quote": subject,
            "age_days": None,
            "zh": (
                "近日你写过:\n"
                f'  "{subject}"\n'
                "道心未泯."
            ),
            "en": (
                "Recently you wrote:\n"
                f'  "{subject}"\n'
                "Your daoxin holds."
            ),
        }
    return {
        "quote": None,
        "age_days": None,
        "zh": "道心未泯.",
        "en": "Your daoxin holds.",
    }


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
