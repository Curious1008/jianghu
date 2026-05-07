---
name: jianghu
description: Wuxia cultivation layer for Claude Code. Every conversation = one breath cultivated. Daily ritual reads your repo and names one heart-demon. Run /jianghu for today's ritual, /jianghu seclusion for breakthroughs, /jianghu archive for past rituals, /jianghu chrome to toggle wuxia theme.
---

# /jianghu — 守山老道

This skill is a wuxia cultivation game layer that lives inside Claude Code.

## Status

PRE-MVP. Repo scaffold only. Build phase begins 2026-05-07.

Design doc frozen at: `references/DESIGN_FROZEN_2026-05-07.md` (TBD: copy from `~/.gstack/projects/harry/`)

## What this will do (per design)

- `/jianghu` — daily ritual. Reads recent git activity, surfaces one 心魔 (heart-demon) diagnosis from 5 patterns, prescribes one 招式 (today's move), encourages with your own past commit messages.
- `/jianghu seclusion` — breakthrough ceremony when 修为 fills. 6-phase: 闭关 → 过此一关 → 渡劫三问 → 突破 → 赐字 → 解锁.
- `/jianghu archive` — list past daily rituals from `~/.jianghu/archive/`.
- `/jianghu chrome` — toggle wuxia chrome theme via tweakcc (or settings.json color patch fallback).
- `/jianghu uninstall` — revert theme, optionally archive `~/.jianghu/`, delete skill state.

## Implementation language

bash + jq + python helpers. Zero `gstack` / `npm` / `brew` dependencies.

## State

`~/.jianghu/` (NOT inside the skill dir). See `references/` for full state schema.

No Claude Code hooks installed. No `~/.claude/settings.json` modification (except optional tweakcc fallback for chrome theme color).

## Distribution

- One-line install: `bash <(curl -fsSL https://raw.githubusercontent.com/Curious1008/jianghu/main/install.sh)`
- Manual: `git clone` + `./setup`
- Audience: vibe coders. The skill is dropped under Reddit/HN panic threads as a one-line install.

## Build order

See `references/DESIGN_FROZEN_2026-05-07.md` for full Week 1-4 plan. Summary:

- Week 1: plumbing (signal source, state, realm progression, R17 width detection)
- Week 2: daily ritual + first-run ceremony
- Week 3: seclusion + breakthrough mechanics
- Week 4: chrome theme + uninstall + install.sh + ship
