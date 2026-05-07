---
name: jianghu
description: Wuxia cultivation layer for Claude Code. Every assistant message = one breath of qi. Daily ritual reads your repo, names one heart-demon, prescribes one move. Run /jianghu for today's ritual, /jianghu seclusion when you're ready to break through to the next realm, /jianghu archive to replay past scrolls, /jianghu chrome to toggle the wuxia theme, /jianghu uninstall to leave the mountain. State lives in ~/.jianghu/. No hooks, no settings.json surgery.
---

# /jianghu — 守山老道

A wuxia cultivation game layer that lives inside Claude Code.

The hermit on the mountain knows your repo, your commits, your push lag, your README age. He never speaks unless you summon him. When you do, he reads the past 7 days of your work, picks one heart-demon, and writes you a 30-minute move for today.

## Commands

| Command | What it does |
|---|---|
| `/jianghu` | Today's daily ritual. 5 sections inside one ASCII scroll: 观 (observed) → 心魔 (heart demon) → 招式 (today's move) → 道心 (your daoxin holds) → 结 (closing). |
| `/jianghu seclusion` | Breakthrough ceremony. Triggered when you've crossed the next realm's breath threshold. 6 phases, three reflective questions, ends with a personalized 名号. |
| `/jianghu archive` | List + replay past rituals from `~/.jianghu/archive/`. |
| `/jianghu chrome` | Toggle the wuxia palette via tweakcc (or fall back to a flag-only marker if tweakcc is missing). |
| `/jianghu uninstall` | Optional archive of `~/.jianghu/` + clean delete. |

## Mechanics

- 1 assistant message in any Claude Code session = 1 息 (breath).
- Realms by cumulative breath: 凡 (0) → 练气 (100) → 筑基 (500) → 金丹 (2,000) → 元婴 (10,000).
- Crossing a threshold doesn't auto-promote — you must run `/jianghu seclusion` to break through. The daily ritual shows a `突破可期` banner once you're eligible.
- Names (`daoxin_name`) are earned at breakthroughs, not at install.

## Implementation

bash + python stdlib only. Zero npm/brew/pip dependencies. Heart-demon LLM call uses the Anthropic Messages API directly via `urllib`. No external SDK.

## State

`~/.jianghu/`:
- `state.json` — realm, journey/realm anchors, ritual count, daoxin name, in_seclusion flag, schema_version
- `config.json` — `enabled_sources`, `chrome_theme`, `frame_style`, `effects`
- `.breath-cache.json` — mtime-keyed assistant-line counts (warm reads <50ms)
- `archive/YYYY-MM-DD.txt` — every rendered scroll, append-only

Single writer per command. Atomic write via tmp+rename. Corrupt JSON is quarantined to `*.corrupt-{ts}` and rebuilt — re-coronation is the recovery path, not silent retry.

## What this is NOT

- **Not a hook.** No `~/.claude/settings.json` patches, no Stop/Notification hooks. Install/uninstall is `cp` and `rm`.
- **Not a daemon.** No background work, no watchers. The hermit only speaks when summoned.
- **Not a productivity tool.** It re-narrates work you're already doing. It does not prescribe what you should be doing.
- **Not Anthropic.** The 心魔 LLM call is direct to the Anthropic Messages API. Set `ANTHROPIC_API_KEY` in your env (any key — your own, a proxy, etc.). Without a key, the daily ritual falls back to silence — every section but 心魔 still works.

## Frozen design

`references/DESIGN_FROZEN_2026-05-07.md` — full design doc, 5-pattern 心魔 prompt spec, R1-R17 visual rules, seclusion choreography, F1-F7 recovery paths.
