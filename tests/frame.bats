#!/usr/bin/env bats
# Tests for frame renderer width invariants.

setup() {
    REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    BIN="$REPO_ROOT/bin"
    TMP="$(mktemp -d)"
}

teardown() { rm -rf "$TMP"; }

# Width helper — counts cells the same way _frame.py does.
cells_per_line() {
    python3 -c "
import sys, unicodedata
def w(c):
    if ord(c) < 0x80:
        return 0 if unicodedata.category(c) in ('Cc','Cf') else 1
    eaw = unicodedata.east_asian_width(c)
    return 2 if eaw in ('W','F') else 1
for line in sys.stdin:
    line = line.rstrip('\n')
    print(sum(w(c) for c in line))
"
}

minimal_payload() {
    local style="${1:-rich}"
    cat <<JSON
{
  "frame_style": "$style",
  "header": {
    "title_zh": "今  日  江  湖",
    "title_en": "T O D A Y",
    "status_line": "练气 · 100 息 · 5%"
  },
  "sections": [
    {
      "label_zh": "观", "label_en": "OBSERVED", "deco": "─── {} ───",
      "blocks": [{"zh": ["过去七日 commit 5 次."], "en": ["5 commits in 7 days."]}]
    },
    {
      "label_zh": "心魔", "label_en": "HEART DEMON", "deco": "╲╲ {} ╱╱",
      "blocks": [{"zh": ["你在拖."], "en": ["You are stalling."]}]
    }
  ]
}
JSON
}

@test "rich frame produces fixed-width lines (50 cells outer)" {
    out="$(minimal_payload rich | "$BIN/jianghu-frame")"
    widths="$(printf '%s\n' "$out" | cells_per_line | sort -u)"
    [ "$widths" = "50" ]
}

@test "safe frame produces fixed-width lines (50 cells outer)" {
    out="$(minimal_payload safe | "$BIN/jianghu-frame")"
    widths="$(printf '%s\n' "$out" | cells_per_line | sort -u)"
    [ "$widths" = "50" ]
}

@test "rich frame uses ╔ corners and ║ verticals" {
    out="$(minimal_payload rich | "$BIN/jianghu-frame")"
    echo "$out" | head -1 | grep -q "╔"
    echo "$out" | tail -2 | grep -q "╚"
    echo "$out" | grep -q "║"
}

@test "safe frame uses ASCII corners and pipes" {
    out="$(minimal_payload safe | "$BIN/jianghu-frame")"
    echo "$out" | head -1 | grep -q "^+="
    echo "$out" | tail -2 | grep -q "^+="
    echo "$out" | grep -q "|"
    ! echo "$out" | grep -q "║"
}

@test "long line gets wrapped within budget" {
    payload="$(python3 -c "
import json
print(json.dumps({
  'frame_style': 'rich',
  'header': {'title_zh': 'T', 'title_en': 'T', 'status_line': 's'},
  'sections': [{
    'label_zh':'观','label_en':'OBSERVED','deco':'─── {} ───',
    'blocks':[{
      'zh':['这是一段非常非常非常非常非常非常非常非常非常长的文字, 应该会被自动换行成多行.'],
      'en':['This is an extremely long line that should be hard wrapped into multiple inner-frame lines because it exceeds the inner budget by a wide margin and we should never break the right edge.']
    }]
  }]
}, ensure_ascii=False))")"
    out="$(printf '%s' "$payload" | "$BIN/jianghu-frame")"
    widths="$(printf '%s\n' "$out" | cells_per_line | sort -u)"
    [ "$widths" = "50" ]
}

@test "banners render between header and first section" {
    payload="$(python3 -c "
import json
print(json.dumps({
  'frame_style': 'rich',
  'header': {'title_zh': 'T', 'title_en': 'T', 'status_line': 's'},
  'banners': ['突破可期 / breakthrough is near'],
  'sections': [{
    'label_zh':'观','label_en':'OBSERVED','deco':'─── {} ───',
    'blocks':[{'zh':['x'],'en':['y']}]
  }]
}, ensure_ascii=False))")"
    out="$(printf '%s' "$payload" | "$BIN/jianghu-frame")"
    echo "$out" | grep -q "突破可期"
    # banner appears before 'OBSERVED' section header
    bn_line="$(echo "$out" | grep -n '突破可期' | head -1 | cut -d: -f1)"
    obs_line="$(echo "$out" | grep -n 'OBSERVED' | head -1 | cut -d: -f1)"
    [ "$bn_line" -lt "$obs_line" ]
}

@test "frame renders without sections gracefully" {
    out="$(printf '%s' '{"frame_style":"rich","header":{"title_zh":"a","title_en":"b","status_line":"c"},"sections":[]}' | "$BIN/jianghu-frame")"
    widths="$(printf '%s\n' "$out" | cells_per_line | sort -u)"
    [ "$widths" = "50" ]
}
