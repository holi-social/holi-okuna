#!/bin/bash

# This file is used by the mprocs yaml files in https://gitlab.holi.team/app/holi-meta 

. .venv/bin/activate
pip3 install -r requirements-cli-only.txt
python3 okuna-cli.py up-services-only
