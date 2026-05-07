#!/usr/bin/env bats
# Tests for state-manager.

setup() {
    REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    BIN="$REPO_ROOT/bin"
    TMP="$(mktemp -d)"
    export JIANGHU_HOME="$TMP/jh"
    STATE="$JIANGHU_HOME/state.json"
}

teardown() {
    rm -rf "$TMP"
}

run_state() { "$BIN/jianghu-state" "$@"; }

jq_get() { python3 -c "import json,sys;print(json.load(open(sys.argv[1]))[sys.argv[2]])" "$1" "$2"; }

@test "init creates default state.json with schema_version=1" {
    run run_state init
    [ "$status" -eq 0 ]
    [ -f "$STATE" ]
    [ "$(jq_get "$STATE" schema_version)" = "1" ]
    [ "$(jq_get "$STATE" current_realm)" = "凡" ]
    [ "$(jq_get "$STATE" realm_index)" = "0" ]
    [ "$(jq_get "$STATE" first_run_complete)" = "False" ]
}

@test "init --breath anchors journey/realm to current breath count" {
    run run_state init --breath 4827
    [ "$status" -eq 0 ]
    [ "$(jq_get "$STATE" journey_started_breath)" = "4827" ]
    [ "$(jq_get "$STATE" realm_entered_breath)" = "4827" ]
}

@test "init is idempotent — does not overwrite existing state" {
    run_state init --breath 100
    before="$(cat "$STATE")"
    run run_state init --breath 999
    [ "$status" -eq 0 ]
    [ "$(cat "$STATE")" = "$before" ]
}

@test "get reads a field as JSON" {
    run_state init --breath 234
    run run_state get realm_index
    [ "$status" -eq 0 ]
    [ "$output" = "0" ]
    run run_state get current_realm
    [ "$output" = "\"凡\"" ]
}

@test "get on unknown field exits 1" {
    run_state init
    run run_state get bogus_field
    [ "$status" -eq 1 ]
}

@test "set mutates a field and persists atomically" {
    run_state init
    run run_state set realm_index 1
    [ "$status" -eq 0 ]
    [ "$(jq_get "$STATE" realm_index)" = "1" ]
    run run_state set current_realm '"练气"'
    [ "$(jq_get "$STATE" current_realm)" = "练气" ]
    run run_state set first_run_complete true
    [ "$(jq_get "$STATE" first_run_complete)" = "True" ]
}

@test "set rejects invalid json value" {
    run_state init
    run run_state set realm_index "not-json"
    [ "$status" -eq 1 ]
    [ "$(jq_get "$STATE" realm_index)" = "0" ]
}

@test "F2 recovery — corrupt state.json is quarantined and rebuilt" {
    run_state init --breath 100
    printf 'garbage{not json' >"$STATE"
    run run_state read
    [ "$status" -eq 0 ]
    # Default state restored in memory; quarantine file written.
    quar="$(ls "$JIANGHU_HOME"/state.json.corrupt-* 2>/dev/null | head -1)"
    [ -n "$quar" ]
    grep -q "garbage" "$quar"
    # Subsequent set persists fresh defaults.
    run run_state set ritual_count 1
    [ "$status" -eq 0 ]
    [ "$(jq_get "$STATE" ritual_count)" = "1" ]
    [ "$(jq_get "$STATE" schema_version)" = "1" ]
}

@test "F2 recovery — schema_version mismatch is treated as corrupt" {
    run_state init
    python3 -c "
import json,sys
p=sys.argv[1]
d=json.load(open(p))
d['schema_version']=99
json.dump(d, open(p,'w'))
" "$STATE"
    run run_state read
    [ "$status" -eq 0 ]
    quar="$(ls "$JIANGHU_HOME"/state.json.corrupt-* 2>/dev/null | head -1)"
    [ -n "$quar" ]
}

@test "atomic write — interrupted write does not leave partial state.json" {
    # Use JIANGHU_TEST_WRITE_DELAY to slow the write; kill mid-flight; verify
    # state.json is either the previous content or the new one, never partial.
    run_state init --breath 50
    before="$(cat "$STATE")"
    # Invoke binary directly (not via shell function) so $! is the bash wrapper
    # which immediately execs python. SIGTERM then reaches python's handler.
    JIANGHU_TEST_WRITE_DELAY=2 "$BIN/jianghu-state" set ritual_count 7 &
    pid=$!
    sleep 0.5
    kill -TERM "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    # State file must still parse.
    run python3 -c "import json,sys;json.load(open(sys.argv[1]));print('ok')" "$STATE"
    [ "$status" -eq 0 ]
    [ "$output" = "ok" ]
    # And content must equal `before` (rename never happened).
    [ "$(cat "$STATE")" = "$before" ]
    # No leftover tmp files in the home dir.
    shopt -s nullglob
    leftover=( "$JIANGHU_HOME"/.state.* )
    shopt -u nullglob
    if [ "${#leftover[@]}" -ne 0 ]; then
        echo "leftover tmp files: ${leftover[*]}" >&2
        false
    fi
}

@test "load backfills missing keys added in newer schema_version 1" {
    # Simulate an older v1 state missing the first_run_* keys.
    mkdir -p "$JIANGHU_HOME"
    cat >"$STATE" <<'JSON'
{
  "schema_version": 1,
  "journey_started_at": "2026-05-07T00:00:00Z",
  "journey_started_breath": 0,
  "current_realm": "凡",
  "realm_index": 0,
  "realm_entered_at": "2026-05-07T00:00:00Z",
  "realm_entered_breath": 0,
  "ritual_count": 3
}
JSON
    run run_state get first_run_complete
    [ "$status" -eq 0 ]
    [ "$output" = "false" ]
    run run_state get ritual_count
    [ "$output" = "3" ]
}

@test "read prints valid JSON" {
    run_state init --breath 12
    run run_state read
    [ "$status" -eq 0 ]
    echo "$output" | python3 -c "import json,sys;json.load(sys.stdin);print('ok')"
}
