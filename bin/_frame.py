#!/usr/bin/env python3
"""ASCII frame renderer for the daily ritual scroll.

Design references: v3 mockup (line 671), R5/R13/R17 in the design doc.

Width contract:
- Inner cell width: 48 (R17, narrow-mode terminals).
- Han / CJK punctuation = 2 cells. ASCII = 1 cell.
- Rich style: ╔═╗║╚╝ + ─━ dividers.
- Safe style: ASCII fallback (+ - = | + +).

Input JSON (stdin or --input):
{
  "frame_style": "rich" | "safe",
  "header": {
    "title_zh": "今  日  江  湖",
    "title_en": "T O D A Y  O N  J I A N G H U",
    "status_line": "练气 · 4827 息 · 32%"
  },
  "banners": ["突破可期 / breakthrough is near"],   // optional, top of body
  "sections": [
    {
      "id": "guan",
      "label_zh": "观",
      "label_en": "OBSERVED",
      "deco": "─── {} ───",
      "blocks": [
        {"zh": ["..."], "en": ["..."]}
      ]
    },
    ...
  ],
  "footer_lines": ["告示板今日 — 签待接.", "明日江湖再见."]
}

Output: full rendered scroll on stdout.
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata

INNER_WIDTH = 48


def cell_width(ch: str) -> int:
    if not ch:
        return 0
    if ord(ch) < 0x80:
        return 0 if unicodedata.category(ch) in ("Cc", "Cf") else 1
    eaw = unicodedata.east_asian_width(ch)
    if eaw in ("W", "F"):
        return 2
    if eaw == "A":
        # Ambiguous treated as narrow (R17 default assumption).
        return 1
    return 1


def text_width(s: str) -> int:
    return sum(cell_width(c) for c in s)


def pad_to(s: str, width: int) -> str:
    """Right-pad with spaces to exact `width` cells. Truncates with `…` if long."""
    w = text_width(s)
    if w <= width:
        return s + " " * (width - w)
    # truncate
    out = ""
    used = 0
    for ch in s:
        cw = cell_width(ch)
        if used + cw + 1 > width:
            break
        out += ch
        used += cw
    return out + "…" + " " * max(0, width - used - 1)


def wrap_text(s: str, width: int) -> list[str]:
    """Wrap `s` into lines that each fit in `width` cells.

    On overflow, prefer the last whitespace within the current line so
    Latin words don't split mid-letter ("complete\\n." → "complete." on
    one line). CJK has no spaces, so it falls back to greedy character
    accumulation, which is the correct behavior there. Newlines in the
    input are honored.
    """
    out: list[str] = []
    for raw_line in s.split("\n"):
        if not raw_line:
            out.append("")
            continue
        line = ""
        line_w = 0
        last_space_pos = -1  # index into `line` of the most recent space
        i = 0
        while i < len(raw_line):
            ch = raw_line[i]
            cw = cell_width(ch)
            if line_w + cw > width and line:
                if last_space_pos >= 0:
                    # Break at the recorded space — head ends clean, carry
                    # becomes the start of the new line. The current `ch` is
                    # the next content for the new line; fall through and
                    # append it normally so any space it carries is kept.
                    head = line[:last_space_pos]
                    carry = line[last_space_pos + 1:]
                    out.append(head.rstrip())
                    line = carry
                    line_w = sum(cell_width(c) for c in line)
                    last_space_pos = -1
                else:
                    # No space in this line — char-break (CJK or one long
                    # token). Skip leading spaces on the continuation.
                    out.append(line.rstrip())
                    line = ""
                    line_w = 0
                    last_space_pos = -1
                    while i < len(raw_line) and raw_line[i] == " ":
                        i += 1
                    continue
            if ch == " ":
                last_space_pos = len(line)
            line += ch
            line_w += cw
            i += 1
        if line:
            out.append(line.rstrip())
    return out or [""]


# --- frame chrome ---------------------------------------------------------

CHROME = {
    "rich": {
        "tl": "╔", "tr": "╗", "bl": "╚", "br": "╝",
        "h": "═", "v": "║",
        "ml": "╠", "mr": "╣",
        "rule_thick": "━",
    },
    "safe": {
        "tl": "+", "tr": "+", "bl": "+", "br": "+",
        "h": "=", "v": "|",
        "ml": "+", "mr": "+",
        "rule_thick": "-",
    },
}


def border(style: str, kind: str) -> str:
    """kind in {top, bottom, divider}"""
    c = CHROME[style]
    fill = c["h"] * INNER_WIDTH
    if kind == "top":
        return c["tl"] + fill + c["tr"]
    if kind == "bottom":
        return c["bl"] + fill + c["br"]
    return c["ml"] + fill + c["mr"]


def wrap_inner(style: str, content: str) -> str:
    c = CHROME[style]
    return c["v"] + pad_to(content, INNER_WIDTH) + c["v"]


def blank(style: str) -> str:
    return wrap_inner(style, "")


def centered(style: str, text: str) -> str:
    w = text_width(text)
    pad = max(0, (INNER_WIDTH - w) // 2)
    line = " " * pad + text
    return wrap_inner(style, line)


def section_header(style: str, label_zh: str, label_en: str, deco: str) -> list[str]:
    decorated = deco.format(label_zh) if "{}" in deco else f"{deco} {label_zh} {deco}"
    out: list[str] = []
    out.append(centered(style, decorated))
    out.append(centered(style, label_en))
    out.append(blank(style))
    return out


def render_block(style: str, lines: list[str], indent: int = 4) -> list[str]:
    """Render content lines at `indent` cells in. Wraps to inner-indent budget.

    Hanging-indent preservation: if the source line begins with leading
    spaces (e.g. a quoted line `  "..."`), the same leading is applied to
    every wrapped continuation so quotes stay visually aligned.
    """
    budget = INNER_WIDTH - indent - 2  # right margin = 2
    out: list[str] = []
    for raw in lines:
        leading = len(raw) - len(raw.lstrip(" "))
        if 0 < leading < budget:
            body_budget = budget - leading
            body_lines = wrap_text(raw[leading:], body_budget)
            wrapped = [(" " * leading) + b for b in (body_lines or [""])]
        else:
            wrapped = wrap_text(raw, budget) or [""]
        for w in wrapped:
            out.append(wrap_inner(style, " " * indent + w))
    return out


def thick_rule(style: str) -> str:
    c = CHROME[style]
    rule_w = INNER_WIDTH - 12  # indent 6 each side
    rule = " " * 6 + c["rule_thick"] * rule_w + " " * 6
    return wrap_inner(style, rule)


def render(payload: dict) -> str:
    style = payload.get("frame_style", "rich")
    if style not in CHROME:
        style = "rich"
    header = payload.get("header") or {}
    banners = payload.get("banners") or []
    sections = payload.get("sections") or []
    footer_lines = payload.get("footer_lines") or []

    out: list[str] = []
    out.append(border(style, "top"))
    out.append(blank(style))

    if header.get("title_zh"):
        out.append(centered(style, header["title_zh"]))
    if header.get("title_en"):
        out.append(centered(style, header["title_en"]))
    out.append(blank(style))
    if header.get("status_line"):
        out.append(centered(style, header["status_line"]))
        out.append(blank(style))

    out.append(border(style, "divider"))

    # Banners go just under the header divider.
    if banners:
        out.append(blank(style))
        for b in banners:
            out.append(centered(style, b))
        out.append(blank(style))
        out.append(border(style, "divider"))

    last_idx = len(sections) - 1
    for i, sec in enumerate(sections):
        out.append(blank(style))
        out.extend(
            section_header(
                style,
                sec.get("label_zh", ""),
                sec.get("label_en", ""),
                sec.get("deco", "─── {} ───"),
            )
        )
        for block in sec.get("blocks") or []:
            zh_lines = block.get("zh") or []
            en_lines = block.get("en") or []
            if zh_lines:
                out.extend(render_block(style, zh_lines))
            if en_lines:
                out.append(blank(style))
                out.extend(render_block(style, en_lines))
        out.append(blank(style))
        if i != last_idx:
            out.append(thick_rule(style))

    if footer_lines:
        out.append(border(style, "divider"))
        out.append(blank(style))
        for line in footer_lines:
            out.append(centered(style, line))
        out.append(blank(style))

    out.append(border(style, "bottom"))
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="path to payload JSON (default: stdin)")
    args = parser.parse_args(argv[1:])
    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            payload = json.load(f)
    else:
        payload = json.load(sys.stdin)
    sys.stdout.write(render(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
