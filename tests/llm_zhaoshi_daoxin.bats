#!/usr/bin/env bats
# Tests for LLM wrapper (mock mode), 招式 templates, 道心 quotation.

setup() {
    REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    BIN="$REPO_ROOT/bin"
    TMP="$(mktemp -d)"
}

teardown() { rm -rf "$TMP"; }

# --- LLM wrapper (mock) ---

call_llm() {
    # Pipe body to llm with env vars scoped to the llm process. Usage:
    # call_llm "<body>" "<mock>" [retries]
    local body="$1" mock="$2" retries="${3:-3}"
    printf '%s' "$body" | env JIANGHU_LLM_MOCK="$mock" JIANGHU_LLM_RETRIES="$retries" "$BIN/jianghu-llm"
}

ok_field() {
    echo "$1" | python3 -c "import json,sys;print(json.load(sys.stdin)[sys.argv[1]])" "$2"
}

@test "llm mock returns text on first attempt and ok=true" {
    body='{"system":"sys","user":"usr"}'
    out="$(call_llm "$body" '你在拖. Auth 不是 bug. You are stalling. Auth is not the bug.')"
    [ "$(ok_field "$out" ok)" = "True" ]
    [ "$(ok_field "$out" attempts)" = "1" ]
}

@test "llm mock @FAIL exhausts retries and returns ok=false" {
    out="$(call_llm '{"system":"s","user":"u"}' '@FAIL' 2)"
    [ "$(ok_field "$out" ok)" = "False" ]
    [ "$(ok_field "$out" attempts)" = "2" ]
}

@test "llm rejects output containing question marks" {
    out="$(call_llm '{"system":"s","user":"u"}' '你怕吗? Are you afraid?' 2)"
    [ "$(ok_field "$out" ok)" = "False" ]
    echo "$out" | grep -q "question mark"
}

@test "llm rejects output containing advice tokens" {
    out="$(call_llm '{"system":"s","user":"u"}' '你也许在拖延. You should refactor.' 2)"
    [ "$(ok_field "$out" ok)" = "False" ]
}

@test "llm rejects output without Chinese content" {
    out="$(call_llm '{"system":"s","user":"u"}' 'No Chinese here. Just english.' 2)"
    [ "$(ok_field "$out" ok)" = "False" ]
    echo "$out" | grep -q "no Chinese content"
}

@test "llm rejects output without English mirror" {
    out="$(call_llm '{"system":"s","user":"u"}' '全中文输出, 没有英文.' 2)"
    [ "$(ok_field "$out" ok)" = "False" ]
}

@test "llm @FILE mock loads response from disk" {
    f="$TMP/resp.txt"
    printf '你在拖.\nYou are stalling.\n' >"$f"
    out="$(call_llm '{"system":"s","user":"u"}' "@FILE:$f")"
    [ "$(ok_field "$out" ok)" = "True" ]
}

@test "llm without mock and without ANTHROPIC_API_KEY exits cleanly with ok=false" {
    body='{"system":"s","user":"u"}'
    out="$(unset ANTHROPIC_API_KEY; JIANGHU_LLM_RETRIES=1 printf '%s' "$body" | "$BIN/jianghu-llm")"
    [ "$(echo "$out" | python3 -c 'import json,sys;print(json.load(sys.stdin)["ok"])')" = "False" ]
    echo "$out" | grep -q "ANTHROPIC_API_KEY"
}

# --- 招式 ---

zhaoshi_for() {
    local pat="$1" dir="$2"
    local sigfile="$TMP/sig.json" routefile="$TMP/route.json"
    cat >"$sigfile" <<JSON
{"is_git_repo": true, "commits_in_window": 5,
 "dirs": [{"dir": "$dir", "commits": 5, "last_age_days": 1}],
 "branches": [], "commit_types": [], "todos": 0,
 "readme_age_days": null, "push_lag": null,
 "messages": {"recent_subjects": [], "oldest_meaningful": null},
 "window_days": 7}
JSON
    cat >"$routefile" <<JSON
{"pattern": "$pat", "evidence": {"surface_dir": "$dir", "dominant_dir": "$dir", "rows": [{"dir": "$dir"}]}}
JSON
    "$BIN/jianghu-zhaoshi" --signals "$sigfile" --route "$routefile"
}

@test "zhaoshi P5 mentions surface dir verbatim" {
    out="$(zhaoshi_for P5 frontend)"
    echo "$out" | grep -q "frontend"
    echo "$out" | grep -q "30 分钟"
    echo "$out" | grep -q "30m"
}

@test "zhaoshi P2 names dominant dir" {
    out="$(zhaoshi_for P2 auth)"
    echo "$out" | grep -q "auth"
    echo "$out" | grep -q "CHANGELOG"
}

@test "zhaoshi P3 does not require dir" {
    out="$(zhaoshi_for P3 anything)"
    echo "$out" | grep -q "branch"
}

@test "zhaoshi P4 names top-row dir" {
    out="$(zhaoshi_for P4 server)"
    echo "$out" | grep -q "server"
}

@test "zhaoshi P1 picks top dir" {
    out="$(zhaoshi_for P1 cli)"
    echo "$out" | grep -q "cli"
}

@test "zhaoshi silence is generic and short" {
    out="$(zhaoshi_for silence whatever)"
    echo "$out" | grep -q "看一眼昨日 commit"
    echo "$out" | grep -q "yesterday"
}

# --- 道心 ---

mk_sig_with_msg() {
    local subject="$1" age="$2"
    local sigfile="$TMP/sig.json"
    python3 -c "
import json,sys
sig = {
  'is_git_repo': True, 'commits_in_window': 1,
  'dirs': [], 'branches': [], 'commit_types': [], 'todos': 0,
  'readme_age_days': None, 'push_lag': None,
  'messages': {
     'recent_subjects': ['recent commit one'],
     'oldest_meaningful': {'subject': sys.argv[1], 'age_days': int(sys.argv[2]), 'ts': '2025-01-01T00:00:00Z'} if int(sys.argv[2]) >= 0 else None
  },
  'window_days': 7
}
print(json.dumps(sig, ensure_ascii=False))
" "$subject" "$age" >"$sigfile"
    echo "$sigfile"
}

@test "daoxin quotes oldest_meaningful subject when present" {
    sig="$(mk_sig_with_msg 'make something people actually use and love' 95)"
    out="$("$BIN/jianghu-daoxin" --signals "$sig")"
    echo "$out" | grep -q "make something people actually use"
    echo "$out" | grep -q "道心未泯"
    echo "$out" | grep -q "Your daoxin holds"
}

@test "daoxin age phrasing for 95-day-old commit is 3 months" {
    sig="$(mk_sig_with_msg 'a long meaningful commit message about real intent' 95)"
    out="$("$BIN/jianghu-daoxin" --signals "$sig")"
    echo "$out" | grep -q "3 月前"
    echo "$out" | grep -q "3 months ago"
}

@test "daoxin falls back to recent_subjects when no oldest_meaningful" {
    sig="$(mk_sig_with_msg 'unused' -1)"
    out="$("$BIN/jianghu-daoxin" --signals "$sig")"
    echo "$out" | grep -q "近日你写过"
    echo "$out" | grep -q "recent commit one"
}

@test "daoxin renders bare closing when no commits at all" {
    sigfile="$TMP/sig.json"
    cat >"$sigfile" <<'JSON'
{"is_git_repo": true, "commits_in_window": 0, "dirs": [], "branches": [],
 "commit_types": [], "todos": 0, "readme_age_days": null, "push_lag": null,
 "messages": {"recent_subjects": [], "oldest_meaningful": null}, "window_days": 7}
JSON
    out="$("$BIN/jianghu-daoxin" --signals "$sigfile")"
    zh="$(echo "$out" | python3 -c 'import json,sys;print(json.load(sys.stdin)["zh"])')"
    [ "$zh" = "道心未泯." ]
}

@test "daoxin year-scale phrasing for 400-day-old commit" {
    sig="$(mk_sig_with_msg 'sufficiently long meaningful commit message text here' 400)"
    out="$("$BIN/jianghu-daoxin" --signals "$sig")"
    echo "$out" | grep -q "去年"
    echo "$out" | grep -q "Last year"
}
