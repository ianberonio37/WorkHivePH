#!/bin/sh
# Install WorkHive git hooks for a fresh clone.
# Run once after cloning: bash scripts/install-hooks.sh
#
# Hooks installed:
#   pre-commit  — runs `tools/canonical_status.py` (sub-second, 14 dimensions)
#   pre-push    — runs `release_gate.py --skip-ui --no-seed` (heavy gate)

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOK_DIR="$ROOT/.git/hooks"

if [ ! -d "$HOOK_DIR" ]; then
    echo "Not a git repo (no .git/hooks directory). Aborting."
    exit 1
fi

cp "$ROOT/scripts/pre-commit.sample" "$HOOK_DIR/pre-commit"
chmod +x "$HOOK_DIR/pre-commit"

echo "Installed pre-commit hook."
echo "It runs tools/canonical_status.py (14 dimensions) on every commit."
echo "Bypass with: git commit --no-verify"
