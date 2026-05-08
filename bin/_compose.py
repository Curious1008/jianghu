#!/usr/bin/env python3
"""Compose the daily-ritual frame payload from per-section JSON files.

Glue between orchestrator (bin/jianghu) and the renderer (_frame.py).
Pure data shaping — no I/O beyond reading the input files.

Required:
    --signals   PATH
    --route     PATH
    --observed  PATH      output of _observed.py
    --zhaoshi   PATH      output of _zhaoshi.py
    --daoxin    PATH      output of _daoxin.py
    --realm     PATH      output of `jianghu-realm for <breath>`
    --breath    INT
    --frame-style {rich,safe}
    --demon-text PATH     plain text file with the 心魔 body (ZH then blank then EN)
                          OR pass `--demon-silence` to render the silence stanza.

Optional flags:
    --demon-silence
    --banner BANNER       (repeatable) e.g. "突破可期 / breakthrough is near"
    --guishan             render the 归山 (return-to-mountain) shorter ritual
    --first-run           prepend Phase 1-4 first-run ceremony (山门 / 观息 /
                          立境 / 无名) per design FROZEN 2026-05-07. Realm
                          placement Path A/B/C/D is derived from --breath.

Output: full frame payload JSON on stdout (consumed by _frame.py).
"""
from __future__ import annotations

import argparse
import json
import sys


GUA_FILLED = "☰"
GUA_EMPTY = "☷"
GUA_CELLS = 8


def gua_bar(progress: float) -> str:
    progress = max(0.0, min(1.0, progress))
    filled = round(GUA_CELLS * progress)
    return GUA_FILLED * filled + GUA_EMPTY * (GUA_CELLS - filled)


def split_demon_text(text: str) -> tuple[list[str], list[str]]:
    """Split LLM body into ZH and EN paragraphs at the first blank line."""
    blocks = text.replace("\r\n", "\n").strip().split("\n\n", 1)
    zh = [ln for ln in blocks[0].split("\n")] if blocks else []
    en = [ln for ln in blocks[1].split("\n")] if len(blocks) > 1 else []
    return zh, en


def section(label_zh: str, label_en: str, deco: str, zh_lines: list[str], en_lines: list[str]) -> dict:
    return {
        "label_zh": label_zh,
        "label_en": label_en,
        "deco": deco,
        "blocks": [{"zh": zh_lines, "en": en_lines}],
    }


def load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# --- first-run ceremony --------------------------------------------------

# Path → (realm_index, ZH realm, EN realm, "weight" tone variant)
def first_run_path(breath: int) -> tuple[str, int, str, str]:
    if breath < 100:
        return "A", 0, "凡", "Mortal"
    if breath < 500:
        return "B", 1, "练气", "Qi Refining"
    if breath < 2000:
        return "C", 2, "筑基", "Foundation"
    if breath < 10000:
        return "D金丹", 3, "金丹", "Golden Core"
    return "D元婴", 4, "元婴", "Nascent Soul"


# 山门 ASCII art — uncentered glyphs only. centering is computed at render
# time so the block sits cleanly on the frame's vertical axis instead of
# floating left.
_GATE_GLYPHS = [
    "╱╲",
    "╱  ╲",
    "╱  〇 ╲",
    "━━━╱━━━━━━╲━━━",
    "╱  山  门  ╲",
    "─────────────",
]


def _center_block(lines: list[str]) -> list[str]:
    """Center a multi-line ASCII block as a unit. Each line is centered to
    the widest line's cell width; the whole block is then offset so its
    midpoint lands on the frame's vertical axis (accounting for the
    render_block indent of 4)."""
    import unicodedata

    def _cw(c: str) -> int:
        if ord(c) < 0x80:
            return 0 if unicodedata.category(c) in ("Cc", "Cf") else 1
        return 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1

    def _w(s: str) -> int:
        return sum(_cw(c) for c in s)

    INNER = 48
    RENDER_INDENT = 4  # render_block prepends this
    block_w = max(_w(s) for s in lines)
    # Block's left edge in frame: center the block_w in INNER, then subtract
    # the indent that render_block will add.
    block_offset = max(0, (INNER - block_w) // 2 - RENDER_INDENT)
    out: list[str] = []
    for line in lines:
        gap = max(0, (block_w - _w(line)) // 2)
        out.append(" " * block_offset + " " * gap + line)
    return out


GATE_ART = _center_block(_GATE_GLYPHS)


def realm_box(zh_name: str, en_name: str) -> list[str]:
    """Render a realm-placement box. Uses cell-width math so CJK + ASCII
    centering line up."""
    import unicodedata

    def cw(c: str) -> int:
        if ord(c) < 0x80:
            return 0 if unicodedata.category(c) in ("Cc", "Cf") else 1
        return 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1

    def w(s: str) -> int:
        return sum(cw(c) for c in s)

    def cell_center(s: str, width: int) -> str:
        gap = max(0, width - w(s))
        left = gap // 2
        right = gap - left
        return " " * left + s + " " * right

    inner = 15  # cells inside │ │
    en_up = en_name.upper()
    top = "    ╭" + "─" * inner + "╮"
    blank = "    │" + " " * inner + "│"
    zh_line = "    │" + cell_center(zh_name, inner) + "│"
    en_line = "    │" + cell_center(en_up, inner) + "│"
    bot = "    ╰" + "─" * inner + "╯"
    return [top, blank, zh_line, en_line, blank, bot]


def first_run_sections(breath: int) -> list[dict]:
    path, idx, zh_name, en_name = first_run_path(breath)
    out: list[dict] = []

    # Phase 1 — 山门
    out.append(
        section(
            "山门",
            "THE GATE",
            "─── {} ───",
            GATE_ART + ["", "山门已开."],
            ["The gate opens."],
        )
    )

    # Phase 2 — 观息 (path-aware tone)
    breath_zh = [f"息  {breath:,}"]
    breath_en = [f"breaths  {breath:,}"]
    if path == "A":
        tone_zh = ["你立于山门. 息未满百."]
        tone_en = ["You stand at the gate. The path begins beneath your feet."]
    elif path == "B":
        tone_zh = ["汝非新人. 已久行此路."]
        tone_en = ["You are no newcomer. You walked this path long."]
    elif path == "C":
        tone_zh = ["根基已立."]
        tone_en = ["The foundation already stands."]
    elif path == "D金丹":
        tone_zh = ["罕.", "汝行此路已远."]
        tone_en = ["Rare.", "You walked far before this."]
    else:  # D元婴
        tone_zh = ["罕中之罕.", "汝已近峰顶."]
        tone_en = ["Rarest of the rare.", "You stand near the summit."]
    out.append(
        section(
            "观息",
            "READING BREATH",
            "─── {} ───",
            breath_zh + [""] + tone_zh,
            breath_en + [""] + tone_en,
        )
    )

    # Phase 3 — 立境 (skipped on Path A)
    if path != "A":
        box = realm_box(zh_name, en_name)
        sparkles = "         ✦   ✦   ✦"
        if path.startswith("D"):
            tone_close_zh = ["无需启蒙. 礼成."]
            tone_close_en = ["No initiation needed. The rite is complete."]
        else:
            tone_close_zh = ["今日为汝立境之日."]
            tone_close_en = ["Today is the day of your placement."]
        out.append(
            section(
                "立境",
                "PLACING REALM",
                "─── {} ───",
                ["依息度量 ─", ""] + box + ["", sparkles, "", *tone_close_zh],
                tone_close_en,
            )
        )

    # Phase 4 — 无名 (skipped on Path A — no naming below 凡 placement)
    if path != "A":
        out.append(
            section(
                "无名",
                "NAMELESS",
                "─── {} ───",
                ['今日为"无名客".', "至下一境, 方有名号."],
                [
                    "Today you are Nameless.",
                    "A name comes at the next realm crossing.",
                ],
            )
        )

    return out


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--signals", required=True)
    p.add_argument("--route", required=True)
    p.add_argument("--observed", required=True)
    p.add_argument("--zhaoshi", required=True)
    p.add_argument("--daoxin", required=True)
    p.add_argument("--realm", required=True)
    p.add_argument("--breath", type=int, required=True)
    p.add_argument("--frame-style", choices=("rich", "safe"), default="rich")
    p.add_argument("--demon-text", help="path to demon body text")
    p.add_argument("--demon-silence", action="store_true")
    p.add_argument("--banner", action="append", default=[])
    p.add_argument("--guishan", action="store_true")
    p.add_argument("--first-run", action="store_true")
    p.add_argument("--harry-note", action="store_true",
                   help="append the keeper's X handle to the closing block")
    args = p.parse_args(argv[1:])

    sig = load(args.signals)
    route = load(args.route)
    observed = load(args.observed)
    zhaoshi = load(args.zhaoshi)
    daoxin = load(args.daoxin)
    realm = load(args.realm)

    realm_name = realm.get("name", "凡")
    realm_en = realm.get("name_en", "Mortal")
    progress = realm.get("progress", 0.0)
    pct = int(round(progress * 100))
    bar = gua_bar(progress)
    status_line = f"{realm_name} · {args.breath} 息 · {bar}  {pct}%"

    sections: list[dict] = []

    if args.first_run:
        sections.extend(first_run_sections(args.breath))
        # Bridge into the standard ritual.
        sections.append(
            section(
                "第一日修行",
                "FIRST DAY OF CULTIVATION",
                "─ {} ─",
                ["今日, 第一日修行 ─"],
                ["Today, your first day of cultivation —"],
            )
        )

    # 观
    sections.append(
        section(
            "观",
            "OBSERVED",
            "─── {} ───",
            observed.get("zh", []),
            observed.get("en", []),
        )
    )

    # 心魔 (skipped in 归山 mode)
    if not args.guishan:
        if args.demon_silence or not args.demon_text:
            zh = ["今日老道无言. 你未入坑."]
            en = ["Today I have nothing to say. You walked clean."]
        else:
            with open(args.demon_text, "r", encoding="utf-8") as f:
                zh, en = split_demon_text(f.read())
        sections.append(
            section("心魔", "HEART DEMON", "╲╲ {} ╱╱", zh, en)
        )

    # 招式
    sections.append(
        section(
            "招式",
            "TODAY'S MOVE",
            "▶▶ {} ◀◀",
            (zhaoshi.get("zh") or "").splitlines() or [""],
            (zhaoshi.get("en") or "").splitlines() or [""],
        )
    )

    # 道心 (skipped in 归山 mode — replaced by single "回来便好" line)
    if args.guishan:
        sections.append(
            section(
                "续",
                "CONTINUE",
                "◇ {} ◇",
                ["回来便好. 修行未断, 修为未减."],
                ["You're back. The practice never broke, the qi was never lost."],
            )
        )
    else:
        sections.append(
            section(
                "道心",
                "YOUR DAOXIN HOLDS",
                "◇ {} ◇",
                (daoxin.get("zh") or "").splitlines() or [""],
                (daoxin.get("en") or "").splitlines() or [""],
            )
        )

    # 结
    closing_zh = ["明日江湖再见."]
    closing_en = ["See you tomorrow on jianghu."]
    if args.harry_note:
        closing_zh.append("")
        closing_zh.append("此卷若有可改之处, 山主在此候音.")
        closing_en.append("")
        closing_en.append("The keeper waits — @Curiousyan08 on X.")
    sections.append(
        section("结", "CLOSING", "─ {} ─", closing_zh, closing_en)
    )

    if args.first_run:
        title_zh = "山  门  初  开"
        title_en = "T H E  G A T E  O P E N S"
    elif args.guishan:
        title_zh = "归  山  仪  式"
        title_en = "R E T U R N   T O   M O U N T A I N"
    else:
        title_zh = "今  日  江  湖"
        title_en = "T O D A Y  O N  J I A N G H U"

    payload = {
        "frame_style": args.frame_style,
        "header": {
            "title_zh": title_zh,
            "title_en": title_en,
            "status_line": status_line,
        },
        "banners": args.banner,
        "sections": sections,
        "footer_lines": [],
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
