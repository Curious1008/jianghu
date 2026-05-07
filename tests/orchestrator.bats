#!/usr/bin/env bats
# End-to-end tests for the jianghu orchestrator.

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
    # Empty projects glob → breath = 0, realm = 凡.
    export JIANGHU_PROJECTS_GLOB="$TMP/no-such/*/*.jsonl"
    export JIANGHU_BREATH_CACHE="$TMP/.breath-cache.json"

    # Skip first-run ceremony for these tests — first-run has its own suite.
    "$BIN/jianghu-state" init --breath 0 >/dev/null
    "$BIN/jianghu-state" set first_run_complete true >/dev/null
}

teardown() { rm -rf "$TMP"; }

commit_at() {
    local days="$1" msg="$2"; shift 2
    for f in "$@"; do
        mkdir -p "$(dirname "$REPO/$f")"
        printf 'l %s\n' "$RANDOM" >>"$REPO/$f"
        git -C "$REPO" add "$f"
    done
    local d
    d="$(python3 -c "import datetime;print((datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(days=$days)).strftime('%Y-%m-%dT%H:%M:%S+0000'))")"
    GIT_AUTHOR_DATE="$d" GIT_COMMITTER_DATE="$d" git -C "$REPO" commit -q -m "$msg"
}

@test "empty repo runs end-to-end and renders silence demon" {
    out="$("$BIN/jianghu" --no-archive --frame-style safe)"
    echo "$out" | grep -q "今  日  江  湖"
    echo "$out" | grep -q "OBSERVED"
    echo "$out" | grep -q "HEART DEMON"
    echo "$out" | grep -q "今日老道无言"
    echo "$out" | grep -q "Today I have nothing to say"
    echo "$out" | grep -q "TODAY'S MOVE"
    echo "$out" | grep -q "看一眼昨日 commit"
}

@test "non-silence pattern uses LLM mock and embeds output" {
    commit_at 1 "feat: x" alpha/x.ts
    commit_at 2 "fix: y" beta/y.ts
    out="$(JIANGHU_LLM_MOCK='你在拖. Auth 不是 bug.

You are stalling. Auth is not the bug.' "$BIN/jianghu" --no-archive --frame-style safe)"
    echo "$out" | grep -q "你在拖"
    echo "$out" | grep -q "You are stalling"
    # 招式 should mention one of the dirs (alpha or beta).
    echo "$out" | grep -E "alpha|beta" >/dev/null
}

@test "LLM failure falls back to silence stanza" {
    commit_at 1 "feat: x" alpha/x.ts
    commit_at 2 "fix: y" beta/y.ts
    out="$(JIANGHU_LLM_MOCK='@FAIL' JIANGHU_LLM_RETRIES=1 "$BIN/jianghu" --no-archive --frame-style safe)"
    echo "$out" | grep -q "今日老道无言"
}

@test "ritual_count increments and last_ritual_at is recorded" {
    "$BIN/jianghu" --no-archive --frame-style safe >/dev/null
    [ "$("$BIN/jianghu-state" get ritual_count)" = "1" ]
    "$BIN/jianghu" --no-archive --frame-style safe >/dev/null
    [ "$("$BIN/jianghu-state" get ritual_count)" = "2" ]
    last="$("$BIN/jianghu-state" get last_ritual_at)"
    [ "$last" != "null" ]
    [ -n "$last" ]
}

@test "archive write appends to today's file" {
    "$BIN/jianghu" --frame-style safe >/dev/null
    today="$(date -u +%Y-%m-%d)"
    [ -f "$JIANGHU_HOME/archive/$today.txt" ]
    grep -q "今  日  江  湖" "$JIANGHU_HOME/archive/$today.txt"
}

@test "guishan-force renders return-to-mountain layout (no demon, has continue section)" {
    out="$("$BIN/jianghu" --no-archive --guishan-force --frame-style safe)"
    echo "$out" | grep -q "归  山  仪  式"
    echo "$out" | grep -q "R E T U R N"
    echo "$out" | grep -q "回来便好"
    echo "$out" | grep -q "CONTINUE"
    # No HEART DEMON section in return-to-mountain mode.
    ! echo "$out" | grep -q "HEART DEMON"
}

@test "auto-guishan triggers when last_ritual_at >72h ago" {
    "$BIN/jianghu-state" init --breath 0 >/dev/null
    "$BIN/jianghu-state" set last_ritual_at '"2026-01-01T00:00:00Z"' >/dev/null
    out="$(JIANGHU_NOW_ISO='2026-01-05T00:00:00Z' "$BIN/jianghu" --no-archive --frame-style safe)"
    echo "$out" | grep -q "归  山"
}

@test "frame style override beats config" {
    "$BIN/jianghu-config" init >/dev/null
    "$BIN/jianghu-config" set frame_style '"rich"' >/dev/null
    out="$("$BIN/jianghu" --no-archive --frame-style safe)"
    echo "$out" | head -1 | grep -q "^+="
    ! echo "$out" | head -1 | grep -q "╔"
}

@test "no banner when next realm exists but breath below threshold" {
    out="$("$BIN/jianghu" --no-archive --frame-style safe)"
    ! echo "$out" | grep -q "突破可期"
}

@test "banner fires when breath is exactly at next-realm threshold" {
    # Fake breath via a synthetic claude-projects fixture: 100 assistant lines.
    local proj="$TMP/projects/p"
    mkdir -p "$proj"
    python3 -c "
out = open('$proj/s.jsonl','w')
for i in range(100):
    out.write('{\"type\":\"assistant\"}\n')
out.close()
"
    export JIANGHU_PROJECTS_GLOB="$TMP/projects/*/*.jsonl"
    out="$("$BIN/jianghu" --no-archive --frame-style safe)"
    echo "$out" | grep -q "突破可期"
}
