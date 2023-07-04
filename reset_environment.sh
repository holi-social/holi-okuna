#!/usr/bin/env bash
set -Eeuo pipefail

echo "🗑 Removing existing venv"
rm -rf .venv

project_python_version=$(cat .python-version)

if command -v pyenv &> /dev/null; then
  echo "✔️ Pyenv found, installing required interpreter"
  pyenv install -s "$project_python_version"
  pyenv local "$project_python_version"
fi

current_python_interpreter=$(python3 -V | sed -e "s/^Python //")

if [[ "$project_python_version" != "$current_python_interpreter" ]]; then
  echo "❌ Current interpreter does not match project requirements, consider using pyenv"
  exit 1
fi

echo "‍🔧 Creating .venv"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-cli-only.txt

echo "✅ All done"
