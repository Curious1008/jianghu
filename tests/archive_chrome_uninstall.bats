#!/usr/bin/env bats
# archive / chrome / uninstall / setup integration.

setup() {
    REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    BIN="$REPO_ROOT/bin"
    TMP="$(mktemp -d)"
    export JIANGHU_HOME="$TMP/home"
    export JIANGHU_REPO_ROOT="$REPO_ROOT"
    "$BIN/jianghu-state" init --breath 0 >/dev/null
}

teardown() { rm -rf "$TMP"; }

# --- archive ---

@test "archive list on empty home shows no-archive message" {
    out="$("$BIN/jianghu-archive" list)"
    echo "$out" | grep -q "No archive yet"
}

@test "archive count is 0 on empty home" {
    [ "$("$BIN/jianghu-archive" count)" = "0" ]
}

@test "archive list shows dates and scroll counts" {
    mkdir -p "$JIANGHU_HOME/archive"
    cat >"$JIANGHU_HOME/archive/2026-05-01.txt" <<'EOF'
=== 2026-05-01T00:00:00Z ===
scroll one
=== 2026-05-01T12:00:00Z ===
scroll two
EOF
    cat >"$JIANGHU_HOME/archive/2026-05-02.txt" <<'EOF'
=== 2026-05-02T00:00:00Z ===
scroll three
EOF
    out="$("$BIN/jianghu-archive" list)"
    echo "$out" | grep -q "2026-05-01"
    echo "$out" | grep -q "2 卷"
    echo "$out" | grep -q "2026-05-02"
    echo "$out" | grep -q "1 卷"
    [ "$("$BIN/jianghu-archive" count)" = "2" ]
}

@test "archive replay last returns most recent date's content" {
    mkdir -p "$JIANGHU_HOME/archive"
    printf '=== A ===\nfirst\n' >"$JIANGHU_HOME/archive/2026-05-01.txt"
    printf '=== B ===\nsecond\n' >"$JIANGHU_HOME/archive/2026-05-03.txt"
    out="$("$BIN/jianghu-archive" replay last)"
    echo "$out" | grep -q "second"
    ! echo "$out" | grep -q "first"
}

@test "archive replay <date> returns specific date" {
    mkdir -p "$JIANGHU_HOME/archive"
    printf '=== X ===\nalpha\n' >"$JIANGHU_HOME/archive/2026-05-01.txt"
    printf '=== Y ===\nbeta\n' >"$JIANGHU_HOME/archive/2026-05-02.txt"
    out="$("$BIN/jianghu-archive" replay 2026-05-01)"
    echo "$out" | grep -q "alpha"
    ! echo "$out" | grep -q "beta"
}

@test "archive replay non-existent date exits non-zero" {
    mkdir -p "$JIANGHU_HOME/archive"
    run "$BIN/jianghu-archive" replay 2099-01-01
    [ "$status" -ne 0 ]
}

# --- chrome ---

@test "chrome status shows off by default" {
    out="$("$BIN/jianghu-chrome" status)"
    echo "$out" | grep -q "chrome_theme: off"
}

@test "chrome on flips flag and references theme path" {
    out="$(JIANGHU_TWEAKCC_BIN=__none__ "$BIN/jianghu-chrome" on)"
    echo "$out" | grep -q "易服"
    echo "$out" | grep -q "themes/jianghu-theme.json"
    out2="$(JIANGHU_TWEAKCC_BIN=__none__ "$BIN/jianghu-chrome" status)"
    echo "$out2" | grep -q "chrome_theme: on"
}

@test "chrome off flips flag back" {
    JIANGHU_TWEAKCC_BIN=__none__ "$BIN/jianghu-chrome" on >/dev/null
    JIANGHU_TWEAKCC_BIN=__none__ "$BIN/jianghu-chrome" off >/dev/null
    out="$(JIANGHU_TWEAKCC_BIN=__none__ "$BIN/jianghu-chrome" status)"
    echo "$out" | grep -q "chrome_theme: off"
}

@test "chrome on with no tweakcc instructs install" {
    out="$(JIANGHU_TWEAKCC_BIN=__none__ "$BIN/jianghu-chrome" on)"
    echo "$out" | grep -q "tweakcc not found"
    echo "$out" | grep -q "npm i -g tweakcc"
}

@test "chrome on with mocked tweakcc reports detection" {
    fake="$TMP/fake-tweakcc"
    printf '#!/bin/sh\necho ok\n' >"$fake"
    chmod +x "$fake"
    out="$(JIANGHU_TWEAKCC_BIN="$fake" "$BIN/jianghu-chrome" on)"
    echo "$out" | grep -q "tweakcc detected"
    echo "$out" | grep -q "$fake"
}

@test "chrome preview prints palette table" {
    out="$("$BIN/jianghu-chrome" preview)"
    echo "$out" | grep -q "palette"
    echo "$out" | grep -q "cinnabar"
    echo "$out" | grep -q "bronze"
    echo "$out" | grep -q "bamboo"
    echo "$out" | grep -q "ash"
}

# --- uninstall ---

@test "uninstall --yes --no-archive deletes home_dir cleanly" {
    mkdir -p "$JIANGHU_HOME/archive"
    printf 'data\n' >"$JIANGHU_HOME/archive/2026-05-01.txt"
    "$BIN/jianghu-uninstall" --yes --no-archive >/dev/null
    [ ! -d "$JIANGHU_HOME" ]
}

@test "uninstall --yes --archive copies home_dir before delete" {
    mkdir -p "$JIANGHU_HOME/archive"
    printf 'data\n' >"$JIANGHU_HOME/archive/2026-05-01.txt"
    target="$TMP/keep"
    JIANGHU_HOME_ARCHIVE_TARGET="$target" "$BIN/jianghu-uninstall" --yes --archive >/dev/null
    [ ! -d "$JIANGHU_HOME" ]
    [ -d "$target" ]
    [ -f "$target/archive/2026-05-01.txt" ]
}

@test "uninstall --keep-state retains files" {
    "$BIN/jianghu-uninstall" --yes --no-archive --keep-state >/dev/null
    [ -d "$JIANGHU_HOME" ]
}

@test "uninstall on non-existent home_dir does not crash" {
    rm -rf "$JIANGHU_HOME"
    run "$BIN/jianghu-uninstall" --yes --no-archive
    [ "$status" -eq 0 ]
}

# --- setup ---

@test "setup --auto initializes config + state" {
    rm -rf "$JIANGHU_HOME"
    out="$("$REPO_ROOT/setup" --auto)"
    echo "$out" | grep -q "frame_style: rich"
    echo "$out" | grep -q "山门已开"
    [ -f "$JIANGHU_HOME/state.json" ]
    [ -f "$JIANGHU_HOME/config.json" ]
}

@test "setup --auto is idempotent (re-running preserves state)" {
    rm -rf "$JIANGHU_HOME"
    "$REPO_ROOT/setup" --auto >/dev/null
    "$BIN/jianghu-state" set ritual_count 5 >/dev/null
    "$REPO_ROOT/setup" --auto >/dev/null
    [ "$("$BIN/jianghu-state" get ritual_count)" = "5" ]
}
