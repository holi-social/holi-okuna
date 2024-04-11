#!/usr/bin/env bash

DEBUG=1
debug () {
  if [ "$DEBUG" = "1" ]; then
    echo "pre-commit (debug) - $1"
  fi
}
 
if [[ -z "${VIRTUAL_ENV}" ]]
then
  debug "sourcing venv activation"
  . "$(dirname -- "$0")/../../.venv/bin/activate"
fi
 
CHANGED_PYTHON_FILES=$(git diff --cached --name-only -z --diff-filter=d -- '*.py')
debug "changed files: ${CHANGED_PYTHON_FILES}"
 
# if we don't have any changed python files, exit with a success
[[ -z "${CHANGED_PYTHON_FILES}" ]] || exit 0
 
for file in ${CHANGED_PYTHON_FILES}; do
  ruff check --force-exclude $file
  ruff format --check --force-exclude $file
done
