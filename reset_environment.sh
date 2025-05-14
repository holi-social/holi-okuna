#!/usr/bin/env bash
set -Eeuo pipefail

echo "🗑️ Removing existing venv"
rm -rf .venv

project_python_version=$(cat .python-version)

if command -v uv &> /dev/null; then
  echo "⚙️ uv found, installing required Python interpreter $project_python_version"
  uv python install --quiet "$project_python_version"
fi

current_python_interpreter=$(python3 -V | sed -e "s/^Python //")

if [[ "$project_python_version" != "$current_python_interpreter" ]]; then
  echo "❌ Current interpreter does not match project requirements, consider using \`uv python\`"
  exit 1
fi

echo "🔧 Creating .venv and installing dependencies"
uv sync --quiet
source .venv/bin/activate

echo "✅ All done"
