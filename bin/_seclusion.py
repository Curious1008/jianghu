#!/usr/bin/env python3
"""Helpers for the /jianghu seclusion (闭关) breakthrough ritual.

Pure data: eligibility, pass summary, three-question text, unlocks table,
breakthrough payload composition. No I/O beyond stdin/stdout.

Subcommands:
    eligibility   --signals --state                  → JSON
    pass-summary  --signals --state                  → {zh:[], en:[]}
    questions                                        → JSON list of {zh, en}
    unlocks       --target-index N                   → {zh:[], en:[]}
    payload       (many flags) → frame payload JSON   stdout

The orchestrator (jianghu-seclusion) wraps these for interactive flow.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
from _realm import REALMS  # noqa: E402  (relies on bin/ on path)
from _compose import realm_box, section, gua_bar  # noqa: E402


THREE_QUESTIONS = [
    {
        "zh": "在你身上, 何处已变?",
        "en": "What in you has changed?",
    },
    {
        "zh": "若代码尽失, 何处最痛?",
        "en": "If your code disappeared, what would hurt most?",
    },
    {
        "zh": "入下一境, 你舍何, 留何?",
        "en": "Entering the next realm, what do you drop, what do you keep?",
    },
]


# Per-target-realm-index unlock blurbs. Ceremonial — actual feature gating
# is v2's concern.
UNLOCKS = {
    1: {
        "zh": ["山中风声, 你已能听见."],
        "en": ["The wind on the mountain, you can hear it now."],
    },
    2: {
        "zh": ["论道告示板 解锁 (将至)."],
        "en": ["The discourse board unlocks (coming soon)."],
    },
    3: {
        "zh": ["道心一栏 显于每日仪式."],
        "en": ["The daoxin section now shows in your daily ritual."],
    },
    4: {
        "zh": ["江湖宗门 隐现 — v2 将启."],
        "en": ["The sects of jianghu show in shadow — v2 awaits."],
    },
}


def eligibility(signals: dict, state: dict) -> dict:
    idx = int(state.get("realm_index", 0) or 0)
    if idx >= len(REALMS) - 1:
        return {
            "eligible": False,
            "reason": "already at the highest realm",
            "current_index": idx,
            "target_index": idx,
            "next_threshold": -1,
            "breath": signals.get("breath_total", 0),
        }
    next_threshold = REALMS[idx + 1][0]
    breath = int(signals.get("breath_total", 0) or 0)
    if breath < next_threshold:
        return {
            "eligible": False,
            "reason": f"breath {breath} below threshold {next_threshold}",
            "current_index": idx,
            "target_index": idx + 1,
            "next_threshold": next_threshold,
            "breath": breath,
        }
    return {
        "eligible": True,
        "reason": "ready to break through",
        "current_index": idx,
        "target_index": idx + 1,
        "next_threshold": next_threshold,
        "breath": breath,
    }


def pass_summary(sig: dict, state: dict) -> dict:
    """3-5 sentence summary of activity in the realm being left.

    Pulls from signals' 7-day window — for a fuller view of the current realm
    we'd need a longer window, deferred to v2. Still beats nothing.
    """
    days = sig.get("window_days", 7)
    n = sig.get("commits_in_window", 0)
    dirs = sig.get("dirs", []) or []
    branches = sig.get("branches", []) or []
    todos = sig.get("todos", 0) or 0
    push_lag = sig.get("push_lag")

    zh: list[str] = []
    en: list[str] = []

    realm_zh = state.get("current_realm", "凡")
    breath = sig.get("breath_total", 0)
    zh.append(f"{realm_zh} 之境, 修为已积 {breath} 息.")
    en.append(f"In the realm of {state.get('current_realm', 'Mortal')}, you cultivated {breath} breaths.")

    zh.append(f"近 {days} 日 commit {n} 次.")
    en.append(f"In the last {days} days you committed {n} times.")

    if dirs:
        top = dirs[0]
        zh.append(f"主 力 在 {top['dir']}/.")
        en.append(f"Most of it landed in {top['dir']}/.")

    if branches:
        unmerged = [b for b in branches if not b.get("merged")]
        if unmerged:
            zh.append(f"未归 branch {len(unmerged)} 支.")
            en.append(f"{len(unmerged)} unmerged branches still wait.")

    if push_lag is not None and push_lag > 0:
        zh.append(f"main 落后远端 {push_lag} 步.")
        en.append(f"Local main lags origin by {push_lag} commits.")

    if todos > 5:
        zh.append(f"TODO {todos} 处.")
        en.append(f"{todos} TODOs across the tree.")

    return {"zh": zh[:5], "en": en[:5]}


def fallback_given_name(sig: dict) -> dict:
    """Deterministic name when LLM is unavailable. Picks a wuxia title +
    top-dir or behavior anchor.
    """
    dirs = sig.get("dirs", []) or []
    top = dirs[0]["dir"] if dirs else None
    todos = sig.get("todos", 0) or 0
    branches = sig.get("branches", []) or []
    unmerged = [b for b in branches if not b.get("merged")]

    if top and top != ".":
        return {
            "zh": f"{top} 隐者",
            "en": f"Hermit of {top}",
            "source": "fallback:top-dir",
        }
    if len(unmerged) >= 2:
        return {
            "zh": "山间散人",
            "en": "Wanderer of the Branches",
            "source": "fallback:multi-branch",
        }
    if todos > 10:
        return {
            "zh": "积尘者",
            "en": "Keeper of Dust",
            "source": "fallback:todo-pile",
        }
    return {
        "zh": "无名客",
        "en": "Nameless Wanderer",
        "source": "fallback:default",
    }


def given_name_prompt(sig: dict, state: dict, target_realm_zh: str, target_realm_en: str) -> dict:
    """Build {system, user} pair for an LLM call to generate the given name."""
    here = THIS_DIR
    repo_root = os.path.dirname(here)
    sys_path = os.path.join(repo_root, "prompts", "given_name_system.txt")
    with open(sys_path, "r", encoding="utf-8") as f:
        system = f.read()
    dirs = sig.get("dirs", [])[:5]
    facts: list[str] = []
    facts.append(f"breaking through to: {target_realm_zh} / {target_realm_en}")
    facts.append(f"breath_total: {sig.get('breath_total', 0)}")
    facts.append(f"commits_in_window: {sig.get('commits_in_window', 0)}")
    facts.append("dirs:")
    for d in dirs:
        facts.append(f"  - {d['dir']}: {d['commits']} commits")
    facts.append(f"todos: {sig.get('todos', 0)}")
    branches = sig.get("branches", [])
    facts.append(f"branches: {len(branches)} ({sum(1 for b in branches if not b.get('merged'))} unmerged)")
    user = (
        "GIT FACTS:\n\n"
        + "\n".join(facts)
        + "\n\nReturn EXACTLY one ZH name (3–5 chars) on one line, then one\n"
        "EN gloss (≤5 words) on the next line. No quotes, no commentary."
    )
    return {"system": system, "user": user}


def parse_given_name(text: str) -> dict | None:
    """LLM output → {zh, en}. Tolerant of extra whitespace + quote noise."""
    if not text:
        return None
    lines = [ln.strip().strip('"').strip("'") for ln in text.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        return None
    zh, en = lines[0], lines[1]
    if not zh or not en:
        return None
    return {"zh": zh, "en": en, "source": "llm"}


def breakthrough_box(zh: str, en: str) -> list[str]:
    """A larger, weightier realm box than first-run's. Used for 突破 phase."""
    box = realm_box(zh, en)
    # Wrap in a wider double-line frame for ceremony.
    return ["", *box, ""]


def unlocks_for(target_index: int) -> dict:
    return UNLOCKS.get(target_index, {"zh": [], "en": []})


def compose_payload(
    sig: dict,
    state: dict,
    answers: list[dict],
    given_name: dict,
    eligibility_info: dict,
    frame_style: str = "rich",
) -> dict:
    """Build the full seclusion scroll payload."""
    target_idx = eligibility_info["target_index"]
    target_zh = REALMS[target_idx][1]
    target_en = REALMS[target_idx][2]
    breath = eligibility_info["breath"]

    sections: list[dict] = []

    # 闭关 entry
    sections.append(
        section(
            "闭关",
            "ENTERING SECLUSION",
            "─── {} ───",
            [f"汝已积修为 {breath} 息.", "足以突破."],
            [f"You have cultivated {breath} breaths.", "Enough to break through."],
        )
    )

    # 过此一关
    summary = pass_summary(sig, state)
    sections.append(
        section(
            "过此一关",
            "THE PASS",
            "─── {} ───",
            summary["zh"],
            summary["en"],
        )
    )

    # 渡劫三问 — render Q + A pairs
    qa_zh: list[str] = []
    qa_en: list[str] = []
    for i, q in enumerate(THREE_QUESTIONS):
        qa_zh.append(f"{i + 1}. {q['zh']}")
        qa_en.append(f"{i + 1}. {q['en']}")
        if i < len(answers):
            ans = answers[i]
            ans_zh = (ans.get("text") or "").strip()
            qa_zh.append(f'   ─ {ans_zh}')
            qa_en.append(f'   ─ {ans_zh}')
        qa_zh.append("")
        qa_en.append("")
    sections.append(
        section(
            "渡劫三问",
            "THREE QUESTIONS",
            "─── {} ───",
            qa_zh,
            qa_en,
        )
    )

    # 突破
    sections.append(
        section(
            "突破",
            "BREAKTHROUGH",
            "─── {} ───",
            breakthrough_box(target_zh, target_en) + ["", "境界已迁."],
            ["", "The realm has shifted."],
        )
    )

    # 赐字
    sections.append(
        section(
            "赐字",
            "GIVEN NAME",
            "◇ {} ◇",
            ["今日为汝赐字 ─", f'  "{given_name["zh"]}"'],
            [f'  "{given_name["en"]}"'],
        )
    )

    # 解锁
    unlocks = unlocks_for(target_idx)
    if unlocks["zh"]:
        sections.append(
            section(
                "解锁",
                "UNLOCKED",
                "─── {} ───",
                unlocks["zh"],
                unlocks["en"],
            )
        )

    pct = 0  # we've just entered the new realm
    bar = gua_bar(0.0)
    status_line = f"{target_zh} · {breath} 息 · {bar}  {pct}%"

    return {
        "frame_style": frame_style,
        "header": {
            "title_zh": "闭  关  突  破",
            "title_en": "S E C L U S I O N",
            "status_line": status_line,
        },
        "banners": [],
        "sections": sections,
        "footer_lines": [],
    }


# --- CLI dispatch ---------------------------------------------------------

def cmd_eligibility(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--signals", required=True)
    p.add_argument("--state", required=True)
    args = p.parse_args(argv)
    with open(args.signals, "r", encoding="utf-8") as f:
        sig = json.load(f)
    with open(args.state, "r", encoding="utf-8") as f:
        state = json.load(f)
    sys.stdout.write(json.dumps(eligibility(sig, state), ensure_ascii=False) + "\n")
    return 0


def cmd_pass_summary(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--signals", required=True)
    p.add_argument("--state", required=True)
    args = p.parse_args(argv)
    with open(args.signals, "r", encoding="utf-8") as f:
        sig = json.load(f)
    with open(args.state, "r", encoding="utf-8") as f:
        state = json.load(f)
    sys.stdout.write(json.dumps(pass_summary(sig, state), ensure_ascii=False) + "\n")
    return 0


def cmd_questions(_argv: list[str]) -> int:
    sys.stdout.write(json.dumps(THREE_QUESTIONS, ensure_ascii=False) + "\n")
    return 0


def cmd_unlocks(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--target-index", type=int, required=True)
    args = p.parse_args(argv)
    sys.stdout.write(json.dumps(unlocks_for(args.target_index), ensure_ascii=False) + "\n")
    return 0


def cmd_given_name_prompt(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--signals", required=True)
    p.add_argument("--state", required=True)
    p.add_argument("--target-zh", required=True)
    p.add_argument("--target-en", required=True)
    args = p.parse_args(argv)
    with open(args.signals, "r", encoding="utf-8") as f:
        sig = json.load(f)
    with open(args.state, "r", encoding="utf-8") as f:
        state = json.load(f)
    sys.stdout.write(
        json.dumps(
            given_name_prompt(sig, state, args.target_zh, args.target_en),
            ensure_ascii=False,
        )
        + "\n"
    )
    return 0


def cmd_parse_name(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--text", required=True)
    args = p.parse_args(argv)
    parsed = parse_given_name(args.text)
    sys.stdout.write(json.dumps(parsed if parsed else {"zh": "", "en": ""}, ensure_ascii=False) + "\n")
    return 0 if parsed else 1


def cmd_fallback_name(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--signals", required=True)
    args = p.parse_args(argv)
    with open(args.signals, "r", encoding="utf-8") as f:
        sig = json.load(f)
    sys.stdout.write(json.dumps(fallback_given_name(sig), ensure_ascii=False) + "\n")
    return 0


def cmd_payload(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--signals", required=True)
    p.add_argument("--state", required=True)
    p.add_argument("--answers", required=True, help="JSON list of {text} per question")
    p.add_argument("--given-name", required=True, help="JSON {zh, en, source}")
    p.add_argument("--eligibility", required=True, help="JSON eligibility object")
    p.add_argument("--frame-style", default="rich", choices=("rich", "safe"))
    args = p.parse_args(argv)
    with open(args.signals, "r", encoding="utf-8") as f:
        sig = json.load(f)
    with open(args.state, "r", encoding="utf-8") as f:
        state = json.load(f)
    with open(args.answers, "r", encoding="utf-8") as f:
        answers = json.load(f)
    with open(args.given_name, "r", encoding="utf-8") as f:
        gn = json.load(f)
    with open(args.eligibility, "r", encoding="utf-8") as f:
        el = json.load(f)
    payload = compose_payload(sig, state, answers, gn, el, frame_style=args.frame_style)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0


COMMANDS = {
    "eligibility": cmd_eligibility,
    "pass-summary": cmd_pass_summary,
    "questions": cmd_questions,
    "unlocks": cmd_unlocks,
    "given-name-prompt": cmd_given_name_prompt,
    "parse-name": cmd_parse_name,
    "fallback-name": cmd_fallback_name,
    "payload": cmd_payload,
}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in COMMANDS:
        sys.stderr.write(f"usage: _seclusion.py {{{ '|'.join(COMMANDS) }}} ...\n")
        return 1
    return COMMANDS[argv[1]](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
