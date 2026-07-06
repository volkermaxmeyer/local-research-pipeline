#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PY=python3.12
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Error: python3.12 not found. Install it with 'brew install python@3.12'."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Creating venv (python3.12)..."
  "$PY" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Updating pip..."
pip install --upgrade pip --quiet

echo "Installing packages (first run takes a few minutes)..."
pip install -r requirements.txt

echo "Downloading spaCy models (German + English, ~1.2 GB total)..."
python -m spacy download de_core_news_lg
python -m spacy download en_core_web_lg

echo
echo "Setup done."
echo "Start the app with: ./run.sh"
