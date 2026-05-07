#!/usr/bin/env bash
# bin/jianghu-detect-width.sh — R17 frame-break detection.
#
# Renders a 48-cell test string using box-drawing chars (East Asian Width
# Ambiguous) above a 48-cell ASCII reference. The user eyeballs alignment and
# picks rich (boxes align) or safe (pure ASCII renderer).
#
# Modes:
#   (default)       interactive prompt; non-tty → rich
#   --rich          force rich (no prompt)
#   --safe          force safe (no prompt)
#   --auto          non-interactive: rich (used by install scripts)
#
# Output: writes frame_style to ~/.jianghu/config.json via jianghu-config.
# Prints the chosen value to stdout.

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mode="prompt"
case "${1:-}" in
    --rich) mode="rich" ;;
    --safe) mode="safe" ;;
    --auto) mode="auto" ;;
    "")     mode="prompt" ;;
    *) printf 'usage: jianghu-detect-width.sh [--rich|--safe|--auto]\n' >&2; exit 1 ;;
esac

render_test_strings() {
    local bar
    bar="$(printf '━%.0s' $(seq 1 46))"
    printf '\n  Box-drawing test (should align with the +-line below):\n\n'
    printf '    ║%s║\n' "$bar"
    printf '    +%s+\n' "$(printf '%0.s-' $(seq 1 46))"
    printf '\n'
}

write_choice() {
    "$here/jianghu-config" init >/dev/null
    "$here/jianghu-config" set frame_style "\"$1\"" >/dev/null
    printf '%s\n' "$1"
}

case "$mode" in
    rich) write_choice rich; exit 0 ;;
    safe) write_choice safe; exit 0 ;;
    auto)
        # Non-interactive default. Most modern terminals (iTerm2, WezTerm, Warp,
        # Alacritty, gnome-terminal default) render ambiguous-width as narrow.
        write_choice rich; exit 0 ;;
    prompt)
        if [ ! -t 0 ] || [ ! -t 1 ]; then
            write_choice rich
            exit 0
        fi
        render_test_strings
        printf '  Do the two lines look the same width? [Y/n] '
        read -r ans
        case "${ans:-y}" in
            n|N|no|NO) write_choice safe ;;
            *)         write_choice rich ;;
        esac ;;
esac
