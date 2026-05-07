# 江湖 (jianghu)

A wuxia cultivation layer for Claude Code. Every conversation is one breath of qi cultivated. Every breakthrough is one realm crossed.

> 守山老道在此. /jianghu 召我.
>
> The mountain hermit waits. /jianghu summons him.

## Install

```sh
bash <(curl -fsSL https://raw.githubusercontent.com/Curious1008/jianghu/main/install.sh)
```

Manually:

```sh
git clone https://github.com/Curious1008/jianghu ~/.claude/skills/jianghu
cd ~/.claude/skills/jianghu && ./setup
```

No `npm`, no `brew`, no `pip`. Bash + python stdlib (already on every macOS/Linux). Zero deps.

## What you get

```
/jianghu              今日江湖 — daily ritual (5 sections, one scroll)
/jianghu seclusion    闭关     — breakthrough ceremony (when realm progress hits 100%)
/jianghu archive      过往修行  — list + replay past rituals
/jianghu chrome       易服     — toggle the wuxia palette
/jianghu uninstall    归山     — clean uninstall
```

## How it works

- Every assistant message in any Claude Code session counts as 1 息 (breath).
- Realms by cumulative breath: **凡** (0) → **练气** (100) → **筑基** (500) → **金丹** (2,000) → **元婴** (10,000).
- Each `/jianghu` reads the past 7 days of your repo, picks a heart-demon pattern (P1-P5), and writes you one concrete 30-minute move for today.
- Names are earned at breakthroughs, not at install. The first breakthrough names you.

The skill never installs hooks, never modifies `~/.claude/settings.json`, never runs in the background. Install + uninstall is `cp` and `rm`.

## A scroll looks like this

```
╔════════════════════════════════════════════════╗
║                                                ║
║                 今  日  江  湖                 ║
║         T O D A Y  O N  J I A N G H U          ║
║                                                ║
║      练气 · 247 息 · ☰☰☰☷☷☷☷☷  37%       ║
║                                                ║
╠════════════════════════════════════════════════╣
║                                                ║
║                  ─── 观 ───                    ║
║                    OBSERVED                    ║
║                                                ║
║    过去 7 日 commit 23 次.                     ║
║    皆在 auth/ 21 次, ./ 2 次.                  ║
║    main 落后远端 14 步.                        ║
║                                                ║
║      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━      ║
║                                                ║
║                   ╲╲ 心魔 ╱╱                   ║
║                  HEART DEMON                   ║
║                                                ║
║    你身陷"重练旧招"之境.                       ║
║    此境之症: 招式磨亮, 内功未增.                ║
║                                                ║
║    You're stuck re-practicing old moves.       ║
║    The blade gets sharper. The qi does not.    ║
║                                                ║
║      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━      ║
║                                                ║
║                   ▶▶ 招式 ◀◀                   ║
║                  TODAY'S MOVE                  ║
║                                                ║
║    停下 refactor. 写一行 CHANGELOG, 关于 auth.  ║
║    30 分钟.                                    ║
║                                                ║
║    Stop refactoring. Write one CHANGELOG line  ║
║    about auth. 30m.                            ║
║                                                ║
║      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━      ║
║                                                ║
║                    ◇ 道心 ◇                    ║
║               YOUR DAOXIN HOLDS                ║
║                                                ║
║    三月前你写过:                               ║
║      "make something people actually use"      ║
║    道心未泯.                                   ║
║                                                ║
╚════════════════════════════════════════════════╝
```

## The 5 heart-demon patterns

The hermit doesn't read your mind. He picks one of 5 rhetorical structures, fills it with real git facts, and lets the structure do the work.

| Pattern | Triggers when | Shape |
|---|---|---|
| **P1** 分层重述 | multi-dir + multi commit-type | hierarchical bullet list of dirs and counts, ending in one verdict |
| **P2** 起名 | one dir holds ≥60% of commits | gives the behavior a wuxia name from the 20-term pool |
| **P3** 举例堆砌 | scattered: ≥3 dirs + ≥2 unmerged branches + ≥5 TODOs | five observations, all pointing at one truth |
| **P4** 矩阵 | ≥3 dirs categorizable | a small frequency table |
| **P5** 反扎心 | active code + cold README (≥30d) | "you think the problem is X, but really it's Y" |
| silence | no signal — clean week | "今日老道无言. 你未入坑." |

Every concrete noun (file path, commit count, time period, branch name) traces back to real git data. The hermit is forbidden to invent.

## Setup

### Required: `ANTHROPIC_API_KEY`

The 心魔 section is the only LLM call. Set `ANTHROPIC_API_KEY` in your env — your own Anthropic key, a proxy, doesn't matter. If unset, that section falls back to silence and the rest of the scroll still works.

```sh
export ANTHROPIC_API_KEY=sk-ant-...
# optional: route through a proxy
export ANTHROPIC_BASE_URL=https://your-proxy.example.com
# optional: pick a different model (default: claude-sonnet-4-5-20250929)
export JIANGHU_LLM_MODEL=claude-sonnet-4-6
```

### Optional: tweakcc for the chrome theme

The wuxia palette is in `themes/jianghu-theme.json`. Without [tweakcc](https://github.com/Piebald-AI/tweakcc), `/jianghu chrome on` just flips a flag and shows you the file. With tweakcc installed, run `tweakcc` after `/jianghu chrome on` and load the palette via the UI.

```sh
npm i -g tweakcc      # optional
/jianghu chrome on
/jianghu chrome preview   # see the palette swatches
```

## State

Everything jianghu knows about you lives in `~/.jianghu/`:

- `state.json` — realm, ritual count, daoxin name, in_seclusion flag, schema_version
- `config.json` — `frame_style`, `chrome_theme`, `enabled_sources`, `effects`
- `.breath-cache.json` — mtime-keyed cache (warm reads <50ms)
- `archive/YYYY-MM-DD.txt` — every rendered scroll, append-only

Single writer per command. Atomic write via tmp+rename. Corrupt JSON gets quarantined as `*.corrupt-{ts}` and rebuilt — re-coronation is the recovery path.

## Uninstall

```sh
/jianghu uninstall          # interactive: optionally archive ~/.jianghu/, then delete
/jianghu uninstall --yes --no-archive   # nuke
```

That's it. No hooks to remove, no `settings.json` to revert (we never touched it).

## Status

MVP. Five commands ship. Outward commands (board, report, demon for Reddit/HN quest matching) are deferred to v2 — the inward loop has to prove retention first.

Run on this repo today. If it surfaces something true, the design works. If it doesn't, the keeper wants to hear about it: [@Curiousyan08](https://x.com/Curiousyan08) on X.

## License

MIT
