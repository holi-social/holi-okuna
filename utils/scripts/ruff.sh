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
 
ruff check
ruff format
