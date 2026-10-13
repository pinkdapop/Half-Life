#!/usr/bin/env bash
# One-time setup: create the public GitHub repo and push. Needs the gh CLI, logged in.
set -euo pipefail
NAME="${1:-halflife}"
git init -b main
git add -A
git commit -m "halflife: initial scaffold"
gh repo create "$NAME" --public --source=. --push \
  --description "Every document decays. halflife tells you how much. Nebius x NVIDIA Global AI Hackathon 2026."
echo "Now paste the repo URL into your Devpost submission."
