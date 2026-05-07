#!/usr/bin/env bats
# First-run ceremony — Path A/B/C/D variants, state placement, idempotency.

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
}

teardown() { rm -rf "$TMP"; }

# Build a synthetic CC projects glob with N assistant lines.
make_breath() {
    local n="$1"
    local proj="$TMP/projects/p"
    mkdir -p "$proj"
    : >"$proj/s.jsonl"
    python3 -c "
n=int(import_n())
" 2>/dev/null || true  # noop guard — we use a simple loop below
    python3 - "$n" "$proj/s.jsonl" <<'PY'
import sys
n = int(sys.argv[1])
with open(sys.argv[2], "w") as f:
    for _ in range(n):
        f.write('{"type":"assistant"}\n')
PY
    export JIANGHU_PROJECTS_GLOB="$TMP/projects/*/*.jsonl"
}

run_ritual() {
    "$BIN/jianghu" --no-archive --frame-style safe "$@"
}

@test "Path A: <100 breaths shows gate but no realm placement" {
    make_breath 47
    out="$(run_ritual)"
    echo "$out" | grep -q "山门已开"
    echo "$out" | grep -q "息  47"
    echo "$out" | grep -q "你立于山门"
    # No 立境 / PLACING REALM section.
    ! echo "$out" | grep -q "PLACING REALM"
    ! echo "$out" | grep -q "NAMELESS"
    # State placement: realm stays 凡 / index 0.
    [ "$("$BIN/jianghu-state" get realm_index)" = "0" ]
    [ "$("$BIN/jianghu-state" get first_run_complete)" = "true" ]
    [ "$("$BIN/jianghu-state" get first_run_breath)" = "47" ]
}

@test "Path B: 100-499 breaths places at qi-refining" {
    make_breath 250
    out="$(run_ritual)"
    echo "$out" | grep -q "山门已开"
    echo "$out" | grep -q "PLACING REALM"
    echo "$out" | grep -q "练气"
    echo "$out" | grep -q "QI REFINING"
    echo "$out" | grep -q "汝非新人"
    echo "$out" | grep -q "Nameless"
    [ "$("$BIN/jianghu-state" get realm_index)" = "1" ]
    [ "$("$BIN/jianghu-state" get current_realm)" = "\"练气\"" ]
    [ "$("$BIN/jianghu-state" get first_run_realm)" = "\"练气\"" ]
}

@test "Path C: 500-1999 breaths places at foundation" {
    make_breath 800
    out="$(run_ritual)"
    echo "$out" | grep -q "筑基"
    echo "$out" | grep -q "FOUNDATION"
    echo "$out" | grep -q "根基已立"
    [ "$("$BIN/jianghu-state" get realm_index)" = "2" ]
}

@test "Path D-jindan: 2000-9999 breaths places at golden core with rare tone" {
    make_breath 5000
    out="$(run_ritual)"
    echo "$out" | grep -q "金丹"
    echo "$out" | grep -q "GOLDEN CORE"
    echo "$out" | grep -q "罕"
    echo "$out" | grep -q "Rare"
    echo "$out" | grep -q "无需启蒙"
    [ "$("$BIN/jianghu-state" get realm_index)" = "3" ]
    [ "$("$BIN/jianghu-state" get first_run_breath)" = "5000" ]
}

@test "Path D-yuanying: 10000+ breaths places at nascent soul" {
    make_breath 12345
    out="$(run_ritual)"
    echo "$out" | grep -q "元婴"
    echo "$out" | grep -q "NASCENT SOUL"
    echo "$out" | grep -q "罕中之罕"
    echo "$out" | grep -q "Rarest"
    [ "$("$BIN/jianghu-state" get realm_index)" = "4" ]
    [ "$("$BIN/jianghu-state" get first_run_breath)" = "12345" ]
}

@test "first-run carries the standard daily ritual sections too" {
    make_breath 250
    out="$(run_ritual)"
    echo "$out" | grep -q "FIRST DAY OF CULTIVATION"
    echo "$out" | grep -q "OBSERVED"
    echo "$out" | grep -q "TODAY'S MOVE"
    echo "$out" | grep -q "CLOSING"
}

@test "second invocation skips first-run ceremony" {
    make_breath 250
    run_ritual >/dev/null
    out="$(run_ritual)"
    ! echo "$out" | grep -q "山门已开"
    ! echo "$out" | grep -q "PLACING REALM"
    ! echo "$out" | grep -q "山  门  初  开"
    # Standard title appears.
    echo "$out" | grep -q "今  日  江  湖"
}

@test "first-run takes priority over guishan even with old last_ritual_at" {
    make_breath 250
    # Manually pre-populate state with a stale last_ritual_at but no first_run.
    "$BIN/jianghu-state" init --breath 0 >/dev/null
    "$BIN/jianghu-state" set last_ritual_at '"2026-01-01T00:00:00Z"' >/dev/null
    out="$(JIANGHU_NOW_ISO='2026-01-05T00:00:00Z' run_ritual)"
    echo "$out" | grep -q "山门已开"
    ! echo "$out" | grep -q "归  山"
}

@test "first-run scroll stays at 50-cell outer width" {
    make_breath 5000
    out="$(run_ritual)"
    widths="$(printf '%s\n' "$out" | python3 -c "
import sys, unicodedata
def w(c):
    if ord(c) < 0x80:
        return 0 if unicodedata.category(c) in ('Cc','Cf') else 1
    eaw = unicodedata.east_asian_width(c)
    return 2 if eaw in ('W','F') else 1
for line in sys.stdin:
    line=line.rstrip('\n')
    print(sum(w(c) for c in line))
" | sort -u)"
    [ "$widths" = "50" ]
}
