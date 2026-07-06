#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "venv fehlt. Lauf erst ./setup.sh"
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

exec streamlit run app.py
