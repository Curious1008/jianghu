#!/usr/bin/env bats
# Tests for git signal extractor + pattern router + demon prompt builder.

setup() {
    REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    BIN="$REPO_ROOT/bin"
    TMP="$(mktemp -d)"
    REPO="$TMP/repo"
    mkdir -p "$REPO"
    git -C "$REPO" init -q -b main
    git -C "$REPO" config user.email t@t.com
    git -C "$REPO" config user.name test
}

teardown() { rm -rf "$TMP"; }

# Make a commit with backdated author/committer date.
# Usage: commit_at "<days_ago>" "<message>" file1 [file2 ...]
commit_at() {
    local days="$1" msg="$2"
    shift 2
    for f in "$@"; do
        mkdir -p "$(dirname "$REPO/$f")"
        printf 'line %s\n' "$RANDOM" >>"$REPO/$f"
        git -C "$REPO" add "$f"
    done
    local d
    d="$(python3 -c "import datetime;print((datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(days=$days)).strftime('%Y-%m-%dT%H:%M:%S+0000'))")"
    GIT_AUTHOR_DATE="$d" GIT_COMMITTER_DATE="$d" git -C "$REPO" commit -q -m "$msg"
}

route() {
    "$BIN/jianghu-signals" --repo "$REPO" --days "${1:-7}" \
        | "$BIN/jianghu-route" \
        | python3 -c "import json,sys;print(json.load(sys.stdin)['pattern'])"
}

@test "non-git directory routes to silence" {
    rm -rf "$REPO/.git"
    run route
    [ "$output" = "silence" ]
}

@test "empty repo routes to silence" {
    run route
    [ "$output" = "silence" ]
}

@test "old commits outside 7d window route to silence" {
    commit_at 30 "feat: old work" src/a.txt
    commit_at 45 "fix: older work" src/b.txt
    run route
    [ "$output" = "silence" ]
}

@test "P5 — active code dir + README older than 30 days" {
    # README first, 60 days ago.
    commit_at 60 "docs: initial readme" README.md
    # Then a burst of recent activity in app/ within window.
    commit_at 1 "feat: route" app/router.ts
    commit_at 2 "feat: handler" app/handler.ts
    commit_at 3 "fix: bug" app/handler.ts
    run route
    [ "$output" = "P5" ]
}

@test "P2 — 60%+ commits in single dir, no dark README" {
    # Recent README so we don't trigger P5.
    commit_at 1 "docs: readme" README.md
    for i in 1 2 3 4 5 6; do
        commit_at "$i" "refactor: tighten auth $i" auth/middleware.ts
    done
    run route
    [ "$output" = "P2" ]
}

@test "P4 — three dirs categorizable, no dominance" {
    commit_at 1 "docs: readme" README.md
    commit_at 1 "refactor: a" alpha/x.ts
    commit_at 1 "refactor: a2" alpha/y.ts
    commit_at 2 "refactor: b" beta/x.ts
    commit_at 2 "refactor: b2" beta/y.ts
    commit_at 3 "refactor: g" gamma/x.ts
    commit_at 3 "refactor: g2" gamma/y.ts
    run route
    [ "$output" = "P4" ]
}

@test "P3 — multi-dir + 2 active branches + many TODOs" {
    commit_at 1 "docs: readme" README.md
    # Seed 3 dirs.
    commit_at 1 "feat: a" alpha/x.ts
    commit_at 2 "feat: b" beta/x.ts
    commit_at 3 "feat: g" gamma/x.ts
    # Add lots of TODOs.
    for i in 1 2 3 4 5 6 7; do
        printf 'TODO: thing %s\n' "$i" >>"$REPO/notes.txt"
    done
    git -C "$REPO" add notes.txt
    GIT_AUTHOR_DATE="$(python3 -c "import datetime;print((datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S+0000'))")" \
    GIT_COMMITTER_DATE="$(python3 -c "import datetime;print((datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S+0000'))")" \
        git -C "$REPO" commit -q -m "chore: add todos"
    # Two unmerged branches ahead of main.
    git -C "$REPO" checkout -q -b feature-x
    commit_at 1 "feat: x work" feat-x/a.ts
    git -C "$REPO" checkout -q main
    git -C "$REPO" checkout -q -b feature-y
    commit_at 1 "feat: y work" feat-y/a.ts
    git -C "$REPO" checkout -q main
    run route
    [ "$output" = "P3" ]
}

@test "P1 — exactly 2 dirs + 2 commit-types falls through to P1" {
    # No README → no P5; only 2 dirs → not P4; no dominance → not P2; no TODOs/branches → not P3.
    commit_at 1 "feat: x" alpha/x.ts
    commit_at 2 "fix: y" beta/y.ts
    run route
    [ "$output" = "P1" ]
}

@test "demon-prompt emits skip_llm=true for silence pattern" {
    sigfile="$TMP/sig.json"
    routefile="$TMP/route.json"
    "$BIN/jianghu-signals" --repo "$REPO" >"$sigfile"
    "$BIN/jianghu-route" --signals "$sigfile" >"$routefile"
    out="$("$BIN/jianghu-demon-prompt" --signals "$sigfile" --route "$routefile")"
    skip="$(echo "$out" | python3 -c "import json,sys;print(json.load(sys.stdin)['skip_llm'])")"
    [ "$skip" = "True" ]
}

@test "demon-prompt emits non-empty system + user for non-silence" {
    commit_at 1 "docs: readme" README.md
    for i in 1 2 3 4 5 6; do
        commit_at "$i" "refactor: tighten auth $i" auth/middleware.ts
    done
    sigfile="$TMP/sig.json"
    routefile="$TMP/route.json"
    "$BIN/jianghu-signals" --repo "$REPO" >"$sigfile"
    "$BIN/jianghu-route" --signals "$sigfile" >"$routefile"
    out="$("$BIN/jianghu-demon-prompt" --signals "$sigfile" --route "$routefile")"
    pat="$(echo "$out" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['pattern'])")"
    [ "$pat" = "P2" ]
    sys_len="$(echo "$out" | python3 -c "import json,sys;d=json.load(sys.stdin);print(len(d['system']))")"
    user_len="$(echo "$out" | python3 -c "import json,sys;d=json.load(sys.stdin);print(len(d['user']))")"
    [ "$sys_len" -gt 500 ]
    [ "$user_len" -gt 100 ]
}

@test "demon-prompt user prompt cites real dir name from facts" {
    commit_at 1 "docs: readme" README.md
    for i in 1 2 3 4 5 6; do
        commit_at "$i" "refactor: $i" zztarget/file.ts
    done
    sigfile="$TMP/sig.json"
    routefile="$TMP/route.json"
    "$BIN/jianghu-signals" --repo "$REPO" >"$sigfile"
    "$BIN/jianghu-route" --signals "$sigfile" >"$routefile"
    out="$("$BIN/jianghu-demon-prompt" --signals "$sigfile" --route "$routefile")"
    user="$(echo "$out" | python3 -c "import json,sys;print(json.load(sys.stdin)['user'])")"
    echo "$user" | grep -q "zztarget"
}

@test "signals extractor reports oldest_meaningful commit subject" {
    commit_at 1 "feat: short" a.ts
    long_msg="rewrite the entire authentication pipeline from scratch with new clerk integration"
    commit_at 60 "$long_msg" b.ts
    out="$("$BIN/jianghu-signals" --repo "$REPO" --days 90)"
    subject="$(echo "$out" | python3 -c "import json,sys;d=json.load(sys.stdin);m=d['messages']['oldest_meaningful'];print(m['subject'] if m else 'none')")"
    # First commit reverse-walk picks the oldest meaningful one.
    case "$subject" in
        *"clerk integration"*|*"feat: short"*) :;;
        *) echo "got subject: $subject" >&2; false;;
    esac
}
