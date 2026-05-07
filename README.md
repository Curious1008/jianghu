# 江湖 (jianghu)

A wuxia cultivation layer for Claude Code. Every conversation is one breath of qi cultivated. Every breakthrough is one realm crossed.

> 守山老道在此. /jianghu 召我.
>
> The mountain hermit waits. /jianghu summons him.

## Install

```
bash <(curl -fsSL https://raw.githubusercontent.com/Curious1008/jianghu/main/install.sh)
```

Or manually:

```
git clone https://github.com/Curious1008/jianghu ~/.claude/skills/jianghu
cd ~/.claude/skills/jianghu
./setup
```

No `gstack`, no `npm`, no `brew`. Just bash + jq + python (which you already have).

## Usage

```
/jianghu              今日江湖 — daily ritual
/jianghu seclusion    闭关 — breakthrough ceremony
/jianghu archive      过往修行 — past rituals
/jianghu chrome       易服 — toggle wuxia chrome theme
/jianghu uninstall    归山 — clean uninstall
```

## How it works

- Every assistant message in any Claude Code session counts as one 息 (breath).
- Breaths accumulate into 修为 (cultivation).
- At thresholds you cross 境界 (realm): 凡 → 练气 → 筑基 → 金丹 → 元婴.
- Each daily `/jianghu` reads your repo, names one 心魔 (heart demon), prescribes one 招式 (today's move).
- Each crossing earns you a 名号 (daoxin name) — given at the next breakthrough, not at install.

The skill never installs hooks, never runs in the background, never modifies your `~/.claude/settings.json`. The hermit only speaks when summoned.

## Status

PRE-MVP. Repo scaffold only. Build phase begins 2026-05-07.

Design doc + visual references frozen 2026-05-07. See:
- `references/jianghu-cover.png` — github cover
- `references/jianghu-moodboard-4panel.png` — visual language
- `references/jianghu-scroll-internals.png` — scroll layout

## License

MIT
