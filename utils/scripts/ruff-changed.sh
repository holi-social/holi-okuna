#!/usr/bin/env bash

GREEN='\033[0;32m'
NOCOLOR='\033[0m'

message() {
  echo -e >&2 "${GREEN}${1}${NOCOLOR}"
}

[[ -z "$(git diff --name-only --diff-filter=d main.. -- "*.py")" ]] && message "No changed files." && echo exit 0

message "==> ruff check"
git diff --name-only -z --diff-filter=d main.. -- "*.py" | xargs -0 ruff check

echo && message "==> ruff format --check"
git diff --name-only -z --diff-filter=d main.. -- "*.py" | xargs -0 ruff format --check