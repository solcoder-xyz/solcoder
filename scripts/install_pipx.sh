#!/usr/bin/env bash
set -euo pipefail

if ! command -v pipx >/dev/null 2>&1; then
  echo "Installing pipx..."
  python3 -m pip install --user pipx
  python3 -m pipx ensurepath || true
  echo "pipx installed. You may need to restart your shell for PATH changes to take effect."
fi

echo "Installing SolCoder via pipx..."
pipx install --force .
echo "Done. Run 'solcoder' from any directory."

