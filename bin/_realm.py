#!/usr/bin/env python3
"""Realm progression engine — pure function over breath count.

Thresholds (from design):
    0      凡   Mortal
    100    练气 Qi Refining
    500    筑基 Foundation
    2000   金丹 Golden Core
    10000  元婴 Nascent Soul

Above 元婴 reserved for v2 — once breath ≥ 10000, the user stays in 元婴 with
progress capped at 1.0.

Usage:
    _realm.py for <breath>          → JSON {index, name, name_en, progress, ...}
    _realm.py thresholds            → JSON list of {index, name, name_en, threshold}
    _realm.py next <breath>         → JSON {index, name, threshold, breaths_to_go}
                                       or null at the cap

`progress` = breaths_in_current_realm / span_to_next_realm. Capped at 1.0 in
the highest realm.
"""
from __future__ import annotations

import json
import sys

REALMS = [
    (0, "凡", "Mortal"),
    (100, "练气", "Qi Refining"),
    (500, "筑基", "Foundation"),
    (2000, "金丹", "Golden Core"),
    (10000, "元婴", "Nascent Soul"),
]


def realm_for(breath: int) -> dict:
    if breath < 0:
        breath = 0
    idx = 0
    for i, (thr, _name, _en) in enumerate(REALMS):
        if breath >= thr:
            idx = i
        else:
            break
    threshold, name, name_en = REALMS[idx]
    if idx + 1 < len(REALMS):
        next_threshold = REALMS[idx + 1][0]
        span = next_threshold - threshold
        progress = min(1.0, max(0.0, (breath - threshold) / span))
        breaths_to_next = max(0, next_threshold - breath)
        next_name = REALMS[idx + 1][1]
    else:
        progress = 1.0
        breaths_to_next = 0
        next_name = None
    return {
        "index": idx,
        "name": name,
        "name_en": name_en,
        "threshold": threshold,
        "breath": breath,
        "progress": round(progress, 6),
        "breaths_to_next": breaths_to_next,
        "next_realm": next_name,
    }


def cmd_for(argv: list[str]) -> int:
    if not argv:
        sys.stderr.write("for requires <breath>\n")
        return 1
    try:
        breath = int(argv[0])
    except ValueError:
        sys.stderr.write("breath must be an integer\n")
        return 1
    sys.stdout.write(json.dumps(realm_for(breath), ensure_ascii=False) + "\n")
    return 0


def cmd_thresholds(_argv: list[str]) -> int:
    out = [
        {"index": i, "name": n, "name_en": en, "threshold": t}
        for i, (t, n, en) in enumerate(REALMS)
    ]
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    return 0


def cmd_next(argv: list[str]) -> int:
    if not argv:
        sys.stderr.write("next requires <breath>\n")
        return 1
    info = realm_for(int(argv[0]))
    if info["next_realm"] is None:
        sys.stdout.write("null\n")
        return 0
    sys.stdout.write(
        json.dumps(
            {
                "index": info["index"] + 1,
                "name": info["next_realm"],
                "threshold": info["threshold"]
                + (info["breaths_to_next"] + (info["breath"] - info["threshold"])),
                "breaths_to_go": info["breaths_to_next"],
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    return 0


COMMANDS = {"for": cmd_for, "thresholds": cmd_thresholds, "next": cmd_next}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in COMMANDS:
        sys.stderr.write("usage: _realm.py {for BREATH|thresholds|next BREATH}\n")
        return 1
    return COMMANDS[argv[1]](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
