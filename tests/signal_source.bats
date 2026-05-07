#!/usr/bin/env bats
# Tests for SignalSource (claude_code impl) + dispatcher.
#
# Run: bats tests/signal_source.bats
# Requires: bats-core, python3, bash 4+.

setup() {
    REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    BIN="$REPO_ROOT/bin"
    FIX_SRC="$BATS_TEST_DIRNAME/fixtures"

    # Per-test sandbox.
    TMP="$(mktemp -d)"
    PROJECTS="$TMP/projects"
    mkdir -p "$PROJECTS"
    cp -R "$FIX_SRC"/proj-a "$FIX_SRC"/proj-b "$PROJECTS/"

    HOME_DIR="$TMP/jianghu-home"
    mkdir -p "$HOME_DIR"

    export JIANGHU_HOME="$HOME_DIR"
    export JIANGHU_BIN="$BIN"
    export JIANGHU_BREATH_CACHE="$HOME_DIR/.breath-cache.json"
    export JIANGHU_PROJECTS_GLOB="$PROJECTS/*/*.jsonl"
}

teardown() {
    rm -rf "$TMP"
}

run_breath() {
    "$BIN/jianghu-breath" "$@"
}

@test "cold scan counts assistant messages across all fixtures" {
    run run_breath
    [ "$status" -eq 0 ]
    [ "$output" = "5" ]
}

@test "cold scan writes cache file with expected schema" {
    run run_breath
    [ "$status" -eq 0 ]
    [ -f "$JIANGHU_BREATH_CACHE" ]
    run python3 -c "import json,sys;d=json.load(open(sys.argv[1]));assert d['version']==1;assert d['total']==5;assert len(d['files'])==2;print('ok')" "$JIANGHU_BREATH_CACHE"
    [ "$status" -eq 0 ]
    [ "$output" = "ok" ]
}

@test "warm hit uses cache (does not re-read unchanged files)" {
    run_breath >/dev/null
    # Mutate file body but keep mtime+size — cache should NOT detect change,
    # so count stays at the cached value (proves cache is hit, not re-scanned).
    f="$PROJECTS/proj-a/session-1.jsonl"
    # Rewrite body to spaces (zero assistant lines) but preserve mtime+size.
    python3 - "$f" <<'PY'
import os, sys
p = sys.argv[1]
st = os.stat(p)
with open(p, "wb") as f:
    f.write(b" " * st.st_size)
os.utime(p, (st.st_atime, st.st_mtime))
PY
    run run_breath
    [ "$status" -eq 0 ]
    [ "$output" = "5" ]
}

@test "mtime change invalidates that file's cache entry" {
    run_breath >/dev/null
    f="$PROJECTS/proj-a/session-1.jsonl"
    # Append two assistant lines + bump mtime.
    printf '{"type":"assistant","timestamp":"2026-06-01T00:00:00Z"}\n{"type":"assistant","timestamp":"2026-06-01T00:00:01Z"}\n' >>"$f"
    run run_breath
    [ "$status" -eq 0 ]
    [ "$output" = "7" ]
}

@test "deleted file is dropped from cache" {
    run_breath >/dev/null
    rm -rf "$PROJECTS/proj-b"
    run run_breath
    [ "$status" -eq 0 ]
    [ "$output" = "3" ]
    run python3 -c "import json,sys;d=json.load(open(sys.argv[1]));assert len(d['files'])==1;print('ok')" "$JIANGHU_BREATH_CACHE"
    [ "$output" = "ok" ]
}

@test "new file is picked up on next call" {
    run_breath >/dev/null
    mkdir -p "$PROJECTS/proj-c"
    printf '{"type":"assistant","timestamp":"2026-07-01T00:00:00Z"}\n' >"$PROJECTS/proj-c/session-3.jsonl"
    run run_breath
    [ "$output" = "6" ]
}

@test "corrupt cache is dropped and recomputed (F6)" {
    printf 'this is not json' >"$JIANGHU_BREATH_CACHE"
    run run_breath
    [ "$status" -eq 0 ]
    [ "$output" = "5" ]
}

@test "missing cache parent dir does not crash" {
    rm -rf "$JIANGHU_HOME"
    export JIANGHU_BREATH_CACHE="$JIANGHU_HOME/.breath-cache.json"
    run run_breath
    [ "$status" -eq 0 ]
    [ "$output" = "5" ]
}

@test "since_iso filter bypasses cache and counts only newer assistant lines" {
    run "$BIN/jianghu-breath" "2026-03-01T00:00:00Z"
    [ "$status" -eq 0 ]
    [ "$output" = "1" ]
}

@test "dispatcher rejects invalid source name (path-injection defense)" {
    cat >"$JIANGHU_HOME/config.json" <<'JSON'
{"enabled_sources": ["../evil"]}
JSON
    run run_breath
    [ "$status" -eq 0 ]
    [ "$output" = "0" ]
    [ -f "$JIANGHU_HOME/.last-signal-error" ]
    grep -q "rejected source name" "$JIANGHU_HOME/.last-signal-error"
}

@test "dispatcher logs missing impl but does not crash" {
    cat >"$JIANGHU_HOME/config.json" <<'JSON'
{"enabled_sources": ["claude_code", "cursor"]}
JSON
    run run_breath
    [ "$status" -eq 0 ]
    [ "$output" = "5" ]
    grep -q "missing source impl" "$JIANGHU_HOME/.last-signal-error"
}

@test "empty projects glob returns 0 with no error" {
    rm -rf "$PROJECTS"/*
    run run_breath
    [ "$status" -eq 0 ]
    [ "$output" = "0" ]
}
