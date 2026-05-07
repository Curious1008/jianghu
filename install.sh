#!/usr/bin/env bash
# /jianghu install one-liner
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/Curious1008/jianghu/main/install.sh)

set -euo pipefail

JIANGHU_REPO="https://github.com/Curious1008/jianghu"
JIANGHU_DIR="${HOME}/.claude/skills/jianghu"

# Sanity: ~/.claude/skills/ must exist (Claude Code installed)
if [ ! -d "${HOME}/.claude/skills" ]; then
    echo "Claude Code skills directory not found at ~/.claude/skills/"
    echo "Install Claude Code first: https://claude.com/claude-code"
    exit 1
fi

# Already installed?
if [ -d "${JIANGHU_DIR}" ]; then
    echo "/jianghu already installed at ${JIANGHU_DIR}"
    echo "To update: cd ${JIANGHU_DIR} && git pull && ./setup"
    exit 0
fi

echo "归山而来. 拉取江湖..."
echo "Cloning ${JIANGHU_REPO} to ${JIANGHU_DIR}..."
git clone --depth 1 "${JIANGHU_REPO}" "${JIANGHU_DIR}"

cd "${JIANGHU_DIR}"
./setup

echo ""
echo "山门已开. Type /jianghu in Claude Code to begin."
