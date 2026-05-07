#!/usr/bin/env bats
# /jianghu seclusion — eligibility, happy path, F5 recovery, fallback name.

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
    export JIANGHU_BREATH_CACHE="$TMP/.breath-cache.json"

    "$BIN/jianghu-state" init --breath 0 >/dev/null
    "$BIN/jianghu-state" set first_run_complete true >/dev/null
}

teardown() { rm -rf "$TMP"; }

make_breath() {
    local n="$1"
    local proj="$TMP/projects/p"
    mkdir -p "$proj"
    python3 - "$n" "$proj/s.jsonl" <<'PY'
import sys
n = int(sys.argv[1])
with open(sys.argv[2], "w") as f:
    for _ in range(n):
        f.write('{"type":"assistant"}\n')
PY
    export JIANGHU_PROJECTS_GLOB="$TMP/projects/*/*.jsonl"
}

write_answers() {
    local path="$TMP/answers.txt"
    printf 'I learned to ship.\nThe README.\nDrop polish, keep one path.\n' >"$path"
    printf '%s' "$path"
}

state_get() {
    "$BIN/jianghu-state" get "$1"
}

# --- eligibility ---

@test "below threshold prints cultivation-incomplete and does nothing" {
    make_breath 50
    out="$("$BIN/jianghu-seclusion" --no-archive 2>&1)"
    echo "$out" | grep -q "修为未满"
    echo "$out" | grep -q "Cultivation incomplete"
    [ "$(state_get realm_index)" = "0" ]
    [ "$(state_get in_seclusion)" = "false" ]
}

@test "at nascent-soul cap prints cap-message" {
    make_breath 50000
    "$BIN/jianghu-state" set realm_index 4 >/dev/null
    out="$("$BIN/jianghu-seclusion" --no-archive 2>&1)"
    echo "$out" | grep -q "修为已极"
    echo "$out" | grep -q "v2"
    [ "$(state_get realm_index)" = "4" ]
}

# --- happy paths ---

@test "Path mortal-to-qi-refining happy path advances realm and persists name" {
    make_breath 150
    answers="$(write_answers)"
    out="$(JIANGHU_LLM_MOCK="重练剑客
Sharpener of Old Blades" "$BIN/jianghu-seclusion" --no-archive --frame-style safe --answers "$answers")"
    echo "$out" | grep -q "ENTERING SECLUSION"
    echo "$out" | grep -q "THE PASS"
    echo "$out" | grep -q "THREE QUESTIONS"
    echo "$out" | grep -q "BREAKTHROUGH"
    echo "$out" | grep -q "GIVEN NAME"
    echo "$out" | grep -q "UNLOCKED"
    echo "$out" | grep -q "练气"
    echo "$out" | grep -q "QI REFINING"
    echo "$out" | grep -q "重练剑客"
    [ "$(state_get realm_index)" = "1" ]
    [ "$(state_get current_realm)" = "\"练气\"" ]
    [ "$(state_get daoxin_name)" = "\"重练剑客\"" ]
    [ "$(state_get daoxin_name_en)" = "\"Sharpener of Old Blades\"" ]
    [ "$(state_get in_seclusion)" = "false" ]
}

@test "Path qi-refining-to-foundation advances realm_index 1 to 2" {
    make_breath 600
    "$BIN/jianghu-state" set realm_index 1 >/dev/null
    answers="$(write_answers)"
    JIANGHU_LLM_MOCK='@FAIL' "$BIN/jianghu-seclusion" --no-archive --frame-style safe --answers "$answers" >/dev/null
    [ "$(state_get realm_index)" = "2" ]
}

@test "answers are persisted into state.seclusion_answers during flow then cleared" {
    make_breath 150
    answers="$(write_answers)"
    JIANGHU_LLM_MOCK='@FAIL' "$BIN/jianghu-seclusion" --no-archive --frame-style safe --answers "$answers" >/dev/null
    # After completion, seclusion_answers is cleared.
    [ "$(state_get seclusion_answers)" = "[]" ]
    [ "$(state_get seclusion_started_at)" = "null" ]
}

@test "answer text appears in the rendered scroll" {
    make_breath 150
    path="$TMP/a.txt"
    printf 'I shipped daily.\nThe brand voice.\nKeep silence drop urgency.\n' >"$path"
    out="$(JIANGHU_LLM_MOCK='@FAIL' "$BIN/jianghu-seclusion" --no-archive --frame-style safe --answers "$path")"
    echo "$out" | grep -q "I shipped daily"
    echo "$out" | grep -q "brand voice"
    echo "$out" | grep -q "Keep silence"
}

# --- given name ---

@test "given-name LLM failure falls back to deterministic name" {
    make_breath 150
    git -C "$REPO" config user.email t@t.com
    git -C "$REPO" config user.name t
    # One commit so dirs has a top entry.
    mkdir -p "$REPO/auth"
    printf 'x\n' >"$REPO/auth/m.ts"
    git -C "$REPO" add auth/m.ts
    GIT_AUTHOR_DATE="$(date -u +%Y-%m-%dT%H:%M:%S+0000)" \
    GIT_COMMITTER_DATE="$(date -u +%Y-%m-%dT%H:%M:%S+0000)" \
    git -C "$REPO" commit -q -m "feat: a"
    answers="$(write_answers)"
    out="$(JIANGHU_LLM_MOCK='@FAIL' "$BIN/jianghu-seclusion" --no-archive --frame-style safe --answers "$answers")"
    # fallback_given_name picks `auth 隐者` for top-dir auth.
    echo "$out" | grep -q "auth 隐者"
    [ "$(state_get daoxin_name)" = "\"auth 隐者\"" ]
}

@test "given-name LLM with valid 2-line output is parsed" {
    make_breath 150
    answers="$(write_answers)"
    out="$(JIANGHU_LLM_MOCK="文心隐者
Hermit of Words" "$BIN/jianghu-seclusion" --no-archive --frame-style safe --answers "$answers")"
    echo "$out" | grep -q "文心隐者"
    [ "$(state_get daoxin_name)" = "\"文心隐者\"" ]
    [ "$(state_get daoxin_name_en)" = "\"Hermit of Words\"" ]
}

# --- F5 recovery ---

@test "in-progress seclusion older than 24h auto-exits" {
    make_breath 150
    "$BIN/jianghu-state" set in_seclusion true >/dev/null
    "$BIN/jianghu-state" set seclusion_started_at '"2026-01-01T00:00:00Z"' >/dev/null
    "$BIN/jianghu-state" set seclusion_target_realm 1 >/dev/null
    "$BIN/jianghu-state" set seclusion_answers '[]' >/dev/null
    out="$(JIANGHU_NOW_ISO='2026-01-05T00:00:00Z' "$BIN/jianghu-seclusion" --no-archive --frame-style safe </dev/null 2>&1)"
    echo "$out" | grep -q "自动出关"
    echo "$out" | grep -q "Auto-exited"
    [ "$(state_get in_seclusion)" = "false" ]
    [ "$(state_get seclusion_answers)" = "[]" ]
    [ "$(state_get realm_index)" = "0" ]
}

@test "--exit-no-breakthrough clears in-progress seclusion" {
    make_breath 150
    "$BIN/jianghu-state" set in_seclusion true >/dev/null
    "$BIN/jianghu-state" set seclusion_target_realm 1 >/dev/null
    "$BIN/jianghu-state" set seclusion_answers '[{"q_index":0,"text":"x"}]' >/dev/null
    out="$("$BIN/jianghu-seclusion" --no-archive --exit-no-breakthrough 2>&1)"
    echo "$out" | grep -q "出关"
    [ "$(state_get in_seclusion)" = "false" ]
    [ "$(state_get seclusion_answers)" = "[]" ]
    [ "$(state_get realm_index)" = "0" ]
}

@test "--restart wipes prior partial answers and starts over" {
    make_breath 150
    "$BIN/jianghu-state" set in_seclusion true >/dev/null
    "$BIN/jianghu-state" set seclusion_target_realm 1 >/dev/null
    "$BIN/jianghu-state" set seclusion_started_at "\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" >/dev/null
    "$BIN/jianghu-state" set seclusion_answers '[{"q_index":0,"text":"old answer"}]' >/dev/null
    answers="$(write_answers)"
    out="$(JIANGHU_LLM_MOCK='@FAIL' "$BIN/jianghu-seclusion" --no-archive --frame-style safe --restart --answers "$answers")"
    ! echo "$out" | grep -q "old answer"
    [ "$(state_get realm_index)" = "1" ]
}

@test "resume picks up at next unanswered question" {
    make_breath 150
    "$BIN/jianghu-state" set in_seclusion true >/dev/null
    "$BIN/jianghu-state" set seclusion_target_realm 1 >/dev/null
    "$BIN/jianghu-state" set seclusion_started_at "\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" >/dev/null
    "$BIN/jianghu-state" set seclusion_answers '[{"q_index":0,"text":"a1 saved"},{"q_index":1,"text":"a2 saved"}]' >/dev/null
    # Provide just the third answer.
    path="$TMP/a3.txt"
    printf 'a3 fresh\n' >"$path"
    out="$(JIANGHU_LLM_MOCK='@FAIL' "$BIN/jianghu-seclusion" --no-archive --frame-style safe --resume --answers "$path")"
    echo "$out" | grep -q "a1 saved"
    echo "$out" | grep -q "a2 saved"
    echo "$out" | grep -q "a3 fresh"
    [ "$(state_get realm_index)" = "1" ]
}

# --- archive ---

@test "archive write appends seclusion entry" {
    make_breath 150
    answers="$(write_answers)"
    JIANGHU_LLM_MOCK='@FAIL' "$BIN/jianghu-seclusion" --frame-style safe --answers "$answers" >/dev/null
    today="$(date -u +%Y-%m-%d)"
    [ -f "$JIANGHU_HOME/archive/$today.txt" ]
    grep -q "seclusion" "$JIANGHU_HOME/archive/$today.txt"
    grep -q "BREAKTHROUGH" "$JIANGHU_HOME/archive/$today.txt"
}

# --- width invariant ---

@test "seclusion scroll keeps 50-cell outer width" {
    make_breath 150
    answers="$(write_answers)"
    out="$(JIANGHU_LLM_MOCK='@FAIL' "$BIN/jianghu-seclusion" --no-archive --frame-style safe --answers "$answers")"
    widths="$(printf '%s\n' "$out" | python3 -c "
import sys, unicodedata
def w(c):
    if ord(c) < 0x80:
        return 0 if unicodedata.category(c) in ('Cc','Cf') else 1
    eaw = unicodedata.east_asian_width(c)
    return 2 if eaw in ('W','F') else 1
for line in sys.stdin:
    line = line.rstrip('\n')
    print(sum(w(c) for c in line))
" | sort -u)"
    [ "$widths" = "50" ]
}
