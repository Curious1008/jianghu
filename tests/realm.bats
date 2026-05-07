#!/usr/bin/env bats
# Tests for realm progression engine — pure function, no I/O.
#
# Note: bats <1.14 mangles CJK in @test names, so test titles are ASCII-only;
# the assertions still verify CJK names in output.

setup() {
    REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
    BIN="$REPO_ROOT/bin"
}

field() {
    "$BIN/jianghu-realm" for "$1" | python3 -c "import json,sys;print(json.dumps(json.load(sys.stdin)[sys.argv[1]],ensure_ascii=False))" "$2"
}

@test "0 breaths -> mortal at index 0, next is qi-refining at 100" {
    [ "$(field 0 name)" = '"凡"' ]
    [ "$(field 0 index)" = '0' ]
    [ "$(field 0 next_realm)" = '"练气"' ]
    [ "$(field 0 breaths_to_next)" = '100' ]
}

@test "boundary 99 stays mortal, 100 enters qi-refining" {
    [ "$(field 99 name)" = '"凡"' ]
    [ "$(field 100 name)" = '"练气"' ]
    [ "$(field 100 index)" = '1' ]
}

@test "boundary 499 vs 500 enters foundation" {
    [ "$(field 499 name)" = '"练气"' ]
    [ "$(field 500 name)" = '"筑基"' ]
    [ "$(field 500 index)" = '2' ]
}

@test "boundary 1999 vs 2000 enters golden-core" {
    [ "$(field 1999 name)" = '"筑基"' ]
    [ "$(field 2000 name)" = '"金丹"' ]
}

@test "boundary 9999 vs 10000 enters nascent-soul" {
    [ "$(field 9999 name)" = '"金丹"' ]
    [ "$(field 10000 name)" = '"元婴"' ]
}

@test "nascent-soul caps progress at 1.0 with null next_realm" {
    [ "$(field 50000 name)" = '"元婴"' ]
    [ "$(field 50000 progress)" = '1.0' ]
    [ "$(field 50000 next_realm)" = 'null' ]
    [ "$(field 50000 breaths_to_next)" = '0' ]
}

@test "progress within qi-refining at 300 of 400 span equals 0.5" {
    [ "$(field 300 progress)" = '0.5' ]
    [ "$(field 300 breaths_to_next)" = '200' ]
}

@test "progress at exact entry into a realm is 0.0" {
    [ "$(field 100 progress)" = '0.0' ]
    [ "$(field 500 progress)" = '0.0' ]
    [ "$(field 2000 progress)" = '0.0' ]
}

@test "negative breath clamps to mortal" {
    [ "$(field -10 name)" = '"凡"' ]
    [ "$(field -10 progress)" = '0.0' ]
}

@test "thresholds command lists 5 realms" {
    run "$BIN/jianghu-realm" thresholds
    [ "$status" -eq 0 ]
    n="$(echo "$output" | python3 -c "import json,sys;print(len(json.load(sys.stdin)))")"
    [ "$n" = "5" ]
}

@test "non-integer breath fails" {
    run "$BIN/jianghu-realm" for "abc"
    [ "$status" -ne 0 ]
}

@test "users actual breath count 20856 maps to nascent-soul" {
    [ "$(field 20856 name)" = '"元婴"' ]
}
