#!/bin/bash

# This file is used by the mprocs yaml files in https://gitlab.holi.team/app/holi-meta 

uv sync
. .venv/bin/activate
python3 okuna-cli.py up-services-only
