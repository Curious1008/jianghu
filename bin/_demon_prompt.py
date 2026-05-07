#!/usr/bin/env python3
"""Build the {system, user} prompt pair for the 心魔 LLM call.

Inputs:
    --signals PATH    JSON from _git_signals.py (or stdin)
    --route   PATH    JSON from _pattern_router.py (or stdin if --signals
                      is given on stdin, then --route must be a file)

Output: JSON {"system": "...", "user": "...", "pattern": "P1"|...|"silence",
              "skip_llm": bool} to stdout.

If pattern == "silence", the caller should NOT make an LLM call — render the
silence fallback text directly. We surface that via skip_llm=true and a
preformatted `silence_text` field.

The system prompt is loaded from prompts/heart_demon_system.txt and is
intended to be sent with prompt-cache enabled (it's static across calls).
The user prompt is just the FACTS for this ritual + the pattern instruction.
"""
from __future__ import annotations

import argparse
import json
import os
import sys


SILENCE_TEXT = (
    "今日老道无言. 你未入坑.\n"
    "Today I have nothing to say. You walked clean."
)


def load_json_arg(path: str | None, allow_stdin: bool) -> dict:
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    if allow_stdin:
        return json.load(sys.stdin)
    raise SystemExit("missing required input")


def system_prompt() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(here)
    path = os.path.join(repo_root, "prompts", "heart_demon_system.txt")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def render_facts(sig: dict) -> str:
    """Render git signals into a compact, human-readable fact block for the LLM.

    Layout matches what humans skim — the LLM reads it the same way and pulls
    only the facts present.
    """
    lines: list[str] = []
    lines.append(f"window_days: {sig.get('window_days')}")
    lines.append(f"commits_in_window: {sig.get('commits_in_window')}")
    lines.append(f"main_branch: {sig.get('main_branch', 'main')}")
    lines.append(f"push_lag: {sig.get('push_lag')}")
    lines.append(f"todos_in_tree: {sig.get('todos', 0)}")
    readme_age = sig.get("readme_age_days")
    lines.append(
        "readme_age_days: " + ("none" if readme_age is None else str(readme_age))
    )

    lines.append("")
    lines.append("dirs (most-active first):")
    for d in sig.get("dirs", [])[:8]:
        lines.append(
            f"  - {d['dir']}: {d['commits']} commits, last touched {d['last_age_days']}d ago"
        )

    lines.append("")
    lines.append("commit_types_seen: " + ", ".join(sig.get("commit_types", []) or ["(none)"]))

    lines.append("")
    lines.append("branches:")
    for b in sig.get("branches", []) or []:
        flag = []
        if b.get("merged"):
            flag.append("merged")
        if b.get("ahead", 0) > 0:
            flag.append(f"ahead {b['ahead']}")
        if not flag:
            flag = ["clean"]
        lines.append(
            f"  - {b['name']}: {', '.join(flag)}, last activity {b.get('age_days')}d ago"
        )
    if not sig.get("branches"):
        lines.append("  (none)")

    msgs = sig.get("messages", {}) or {}
    recent = msgs.get("recent_subjects") or []
    if recent:
        lines.append("")
        lines.append("recent_commit_subjects:")
        for s in recent:
            lines.append(f"  - {s}")
    old = msgs.get("oldest_meaningful")
    if old:
        lines.append("")
        lines.append(
            f"oldest_meaningful_commit ({old.get('age_days')}d ago): {old.get('subject')}"
        )

    return "\n".join(lines)


def user_prompt(sig: dict, route: dict) -> str:
    pattern = route.get("pattern", "silence")
    evidence = route.get("evidence", {})
    facts = render_facts(sig)
    if pattern == "silence":
        return ""

    return (
        f"GIT FACTS (the only source of concrete nouns you may use):\n\n"
        f"{facts}\n\n"
        f"---\n\n"
        f"ROUTER PICKED: {pattern}\n"
        f"ROUTER REASON: {route.get('reason', '')}\n"
        f"ROUTER EVIDENCE: {json.dumps(evidence, ensure_ascii=False)}\n\n"
        f"Render the 心魔 body using pattern {pattern} and these facts only. "
        "ZH paragraph first, blank line, then EN mirror. No headers, no fences."
    )


def build(sig: dict, route: dict) -> dict:
    pattern = route.get("pattern", "silence")
    if pattern == "silence":
        return {
            "pattern": "silence",
            "skip_llm": True,
            "silence_text": SILENCE_TEXT,
            "system": "",
            "user": "",
        }
    return {
        "pattern": pattern,
        "skip_llm": False,
        "silence_text": SILENCE_TEXT,
        "system": system_prompt(),
        "user": user_prompt(sig, route),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signals", help="signals JSON file")
    parser.add_argument("--route", help="route JSON file")
    args = parser.parse_args(argv[1:])

    if not args.signals or not args.route:
        sys.stderr.write("both --signals and --route are required\n")
        return 1

    with open(args.signals, "r", encoding="utf-8") as f:
        sig = json.load(f)
    with open(args.route, "r", encoding="utf-8") as f:
        route = json.load(f)

    sys.stdout.write(json.dumps(build(sig, route), ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
