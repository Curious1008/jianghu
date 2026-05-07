#!/usr/bin/env bats
# Day-7 keeper note — appears 7d after first-run, every 30d after.

setup() {
    REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    BIN="$REPO_ROOT/bin"
    TMP="$(mktemp -d)"
    REPO="$TMP/repo"
    mkdir -p "$REPO"
    git -C "$REPO" init -q -b main
    git -C "$REPO" config user.email t@t.com
    git -C "$REPO" config user.name test

    export JIANGHU_HOME="$TMP/home"
    export JIANGHU_REPO="$REPO"
    export JIANGHU_PROJECTS_GLOB="$TMP/no-such/*/*.jsonl"
    export JIANGHU_BREATH_CACHE="$TMP/.bc"

    "$BIN/jianghu-state" init --breath 0 >/dev/null
    "$BIN/jianghu-state" set first_run_complete true >/dev/null
    "$BIN/jianghu-state" set first_run_at '"2026-01-01T00:00:00Z"' >/dev/null
}

teardown() { rm -rf "$TMP"; }

run_at() {
    local now="$1"; shift
    JIANGHU_NOW_ISO="$now" "$BIN/jianghu" --no-archive --frame-style safe "$@"
}

@test "day 6 after first-run: no keeper note" {
    out="$(run_at '2026-01-07T00:00:00Z')"
    ! echo "$out" | grep -q "Curiousyan08"
    [ "$("$BIN/jianghu-state" get last_harry_prompt_at)" = "null" ]
}

@test "day 7 after first-run with null last_prompt: note appears + state stamped" {
    out="$(run_at '2026-01-08T00:00:00Z')"
    echo "$out" | grep -q "Curiousyan08"
    echo "$out" | grep -q "山主在此候音"
    last="$("$BIN/jianghu-state" get last_harry_prompt_at)"
    [ "$last" != "null" ]
    [ -n "$last" ]
}

@test "note shown <30d ago: not re-shown" {
    "$BIN/jianghu-state" set last_harry_prompt_at '"2026-02-01T00:00:00Z"' >/dev/null
    out="$(run_at '2026-02-25T00:00:00Z')"
    ! echo "$out" | grep -q "Curiousyan08"
}

@test "note shown >30d ago: re-shown and state re-stamped" {
    "$BIN/jianghu-state" set last_harry_prompt_at '"2026-02-01T00:00:00Z"' >/dev/null
    out="$(run_at '2026-03-10T00:00:00Z')"
    echo "$out" | grep -q "Curiousyan08"
    last="$("$BIN/jianghu-state" get last_harry_prompt_at)"
    [ "$last" = "\"2026-03-10T00:00:00Z\"" ]
}

@test "first-run mode itself does not show keeper note" {
    "$BIN/jianghu-state" set first_run_complete false >/dev/null
    "$BIN/jianghu-state" set first_run_at null >/dev/null
    out="$("$BIN/jianghu" --no-archive --frame-style safe)"
    ! echo "$out" | grep -q "Curiousyan08"
}

@test "note rendering preserves 50-cell outer width" {
    out="$(run_at '2026-01-15T00:00:00Z')"
    widths="$(printf '%s\n' "$out" | python3 -c "
import sys, unicodedata
def w(c):
    if ord(c) < 0x80: return 0 if unicodedata.category(c) in ('Cc','Cf') else 1
    return 2 if unicodedata.east_asian_width(c) in ('W','F') else 1
for line in sys.stdin:
    line = line.rstrip('\n')
    print(sum(w(c) for c in line))
" | sort -u)"
    [ "$widths" = "50" ]
}
