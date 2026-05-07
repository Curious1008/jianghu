# shellcheck shell=bash
# bin/signal-source-claude_code.sh
#
# SignalSource impl for Claude Code. Sourced by jianghu-breath, not executed.
# Exposes one function: count_breaths_for_source(since_iso).
#
# Test/override hooks (env vars):
#   JIANGHU_BREATH_CACHE  — override cache path (default ~/.jianghu/.breath-cache.json)
#   JIANGHU_PROJECTS_GLOB — override jsonl glob (default ~/.claude/projects/*/*.jsonl)

count_breaths_for_source() {
    local since_iso="${1:-}"
    local here
    here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local helper="$here/_signal-source-claude_code.py"
    local cache="${JIANGHU_BREATH_CACHE:-}"
    local pglob="${JIANGHU_PROJECTS_GLOB:-}"
    python3 "$helper" "$since_iso" "$cache" "$pglob"
}
