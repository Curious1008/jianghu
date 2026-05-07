#!/usr/bin/env bats
# Tests for R17 width detection.

setup() {
    REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    BIN="$REPO_ROOT/bin"
    TMP="$(mktemp -d)"
    export JIANGHU_HOME="$TMP/jh"
    CFG="$JIANGHU_HOME/config.json"
}

teardown() { rm -rf "$TMP"; }

frame_style() { python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['frame_style'])" "$CFG"; }

@test "--rich writes rich" {
    run "$BIN/jianghu-detect-width.sh" --rich
    [ "$status" -eq 0 ]
    [ "$output" = "rich" ]
    [ "$(frame_style)" = "rich" ]
}

@test "--safe writes safe" {
    run "$BIN/jianghu-detect-width.sh" --safe
    [ "$status" -eq 0 ]
    [ "$output" = "safe" ]
    [ "$(frame_style)" = "safe" ]
}

@test "--auto writes rich (non-interactive default)" {
    run "$BIN/jianghu-detect-width.sh" --auto
    [ "$status" -eq 0 ]
    [ "$(frame_style)" = "rich" ]
}

@test "no tty → defaults to rich silently" {
    # bats `run` already pipes stdin, so stdin is not a tty.
    run "$BIN/jianghu-detect-width.sh" </dev/null
    [ "$status" -eq 0 ]
    [ "$(frame_style)" = "rich" ]
}

@test "unknown flag exits 1" {
    run "$BIN/jianghu-detect-width.sh" --bogus
    [ "$status" -eq 1 ]
}

@test "preserves other config fields" {
    "$BIN/jianghu-config" init
    "$BIN/jianghu-config" set chrome_theme '"on"'
    "$BIN/jianghu-detect-width.sh" --safe >/dev/null
    [ "$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['chrome_theme'])" "$CFG")" = "on" ]
    [ "$(frame_style)" = "safe" ]
}
