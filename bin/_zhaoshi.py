#!/usr/bin/env python3
"""Deterministic 招式 (today's move) renderer.

Per design (line 359), 招式 is one concrete small action prescribed based on
the inferred 心魔. Fits in 30 minutes. Bilingual. Imperative voice.

We don't call an LLM for this — the action follows directly from the routed
pattern + one signal fact. Determinism here keeps cost low (心魔 is the only
LLM call) and makes 招式 immune to LLM drift.

Inputs:
    --signals PATH   signals JSON
    --route   PATH   route JSON

Output: {"zh": str, "en": str, "pattern": str}
"""
from __future__ import annotations

import argparse
import json
import sys

# pattern → (zh, en). Templates use {placeholder} fields filled from facts.
TEMPLATES = {
    "P1": (
        "今日只动一处. 选 {dir}. 不开新文件. 30 分钟.",
        "Today, touch one place only. Pick {dir}. No new files. 30m.",
    ),
    "P2": (
        "停下 refactor. 写一行 CHANGELOG, 关于 {dir}. 30 分钟.",
        "Stop refactoring. Write one CHANGELOG line about {dir}. 30m.",
    ),
    "P3": (
        "今日不开新 branch. 选最近一支, 推上去. 30 分钟.",
        "No new branches today. Pick the most recent one. Push it. 30m.",
    ),
    "P4": (
        "选最高那行 — {dir}. 推一个 commit. 别处不碰. 30 分钟.",
        "Pick the top row — {dir}. Land one commit there. Nowhere else. 30m.",
    ),
    "P5": (
        "今日不动 {dir}. 开 README, 改首段. 30 分钟.",
        "Today, don't touch {dir}. Open README, rewrite the first paragraph. 30m.",
    ),
    "silence": (
        "今日只做一件: 看一眼昨日 commit. 不必动手.",
        "Today, just one thing: look at yesterday's commit. No work needed.",
    ),
}


def pick_dir(sig: dict, route: dict, pattern: str) -> str:
    """Pick the dir to feature based on the pattern's evidence."""
    ev = route.get("evidence", {}) or {}
    if pattern == "P5":
        return ev.get("surface_dir") or top_dir(sig) or "src"
    if pattern == "P2":
        return ev.get("dominant_dir") or top_dir(sig) or "src"
    if pattern == "P4":
        rows = ev.get("rows") or []
        if rows:
            return rows[0].get("dir") or "src"
        return top_dir(sig) or "src"
    if pattern == "P1":
        return top_dir(sig) or "src"
    return top_dir(sig) or "src"


def top_dir(sig: dict) -> str:
    dirs = sig.get("dirs", []) or []
    return dirs[0]["dir"] if dirs else ""


def render(sig: dict, route: dict) -> dict:
    pattern = route.get("pattern", "silence")
    if pattern not in TEMPLATES:
        pattern = "silence"
    zh_tmpl, en_tmpl = TEMPLATES[pattern]
    chosen = pick_dir(sig, route, pattern)
    return {
        "pattern": pattern,
        "zh": zh_tmpl.format(dir=chosen),
        "en": en_tmpl.format(dir=chosen),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signals", required=True)
    parser.add_argument("--route", required=True)
    args = parser.parse_args(argv[1:])
    with open(args.signals, "r", encoding="utf-8") as f:
        sig = json.load(f)
    with open(args.route, "r", encoding="utf-8") as f:
        route = json.load(f)
    sys.stdout.write(json.dumps(render(sig, route), ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
