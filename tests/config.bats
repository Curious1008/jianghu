#!/usr/bin/env bats
# Tests for config-manager.

setup() {
    REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    BIN="$REPO_ROOT/bin"
    TMP="$(mktemp -d)"
    export JIANGHU_HOME="$TMP/jh"
    CFG="$JIANGHU_HOME/config.json"
}

teardown() { rm -rf "$TMP"; }

run_cfg() { "$BIN/jianghu-config" "$@"; }

py_get() { python3 -c "import json,sys;print(json.dumps(json.load(open(sys.argv[1]))[sys.argv[2]],ensure_ascii=False))" "$1" "$2"; }

@test "init creates config.json with frozen defaults" {
    run run_cfg init
    [ "$status" -eq 0 ]
    [ -f "$CFG" ]
    [ "$(py_get "$CFG" enabled_sources)" = '["claude_code"]' ]
    [ "$(py_get "$CFG" chrome_theme)"  = '"off"' ]
    [ "$(py_get "$CFG" frame_style)"   = '"rich"' ]
    [ "$(py_get "$CFG" effects)"       = '"on"' ]
}

@test "init is idempotent — does not overwrite existing config" {
    run_cfg init
    run_cfg set chrome_theme '"on"'
    before="$(cat "$CFG")"
    run run_cfg init
    [ "$(cat "$CFG")" = "$before" ]
}

@test "get reads field as JSON" {
    run_cfg init
    run run_cfg get enabled_sources
    [ "$output" = '["claude_code"]' ]
    run run_cfg get frame_style
    [ "$output" = '"rich"' ]
}

@test "get unknown field exits 1" {
    run_cfg init
    run run_cfg get bogus
    [ "$status" -eq 1 ]
}

@test "set persists changes" {
    run_cfg init
    run run_cfg set frame_style '"safe"'
    [ "$status" -eq 0 ]
    [ "$(py_get "$CFG" frame_style)" = '"safe"' ]
    run run_cfg set enabled_sources '["claude_code","cursor"]'
    [ "$(py_get "$CFG" enabled_sources)" = '["claude_code", "cursor"]' ]
}

@test "set rejects invalid json" {
    run_cfg init
    run run_cfg set frame_style 'not-json'
    [ "$status" -eq 1 ]
}

@test "corrupt config is quarantined and defaults restored" {
    run_cfg init
    printf 'broken{' >"$CFG"
    out="$(run_cfg get frame_style 2>/dev/null)"
    [ "$out" = '"rich"' ]
    quar="$(ls "$JIANGHU_HOME"/config.json.corrupt-* 2>/dev/null | head -1)"
    [ -n "$quar" ]
}

@test "missing file returns defaults from get" {
    run run_cfg get frame_style
    [ "$status" -eq 0 ]
    [ "$output" = '"rich"' ]
}

@test "unknown user-added keys round-trip" {
    run_cfg init
    run run_cfg set my_custom_key '42'
    [ "$status" -eq 0 ]
    run run_cfg get my_custom_key
    [ "$output" = '42' ]
}
