#!/bin/bash

# This file is used by the mprocs yaml files in https://gitlab.holi.team/app/holi-meta 

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

if [ -z "$GDAL_LIBRARY_PATH" ]; then
    if command_exists brew; then
        export GDAL_LIBRARY_PATH=$(brew --prefix)/lib/libgdal.dylib
    fi
fi

if [ -z "$GEOS_LIBRARY_PATH" ]; then
    if command_exists brew; then
        export GEOS_LIBRARY_PATH=$(brew --prefix)/lib/libgeos_c.dylib
    fi
fi

uv sync
. .venv/bin/activate
. ./.envrc.local
echo "waiting for services"
until docker ps|grep okuna-redis; do
  sleep 1
  echo -n .
done
../wait-for-port.sh 8085
eval "$(gcloud beta emulators pubsub env-init)"
python3 manage.py migrate
python3 manage.py collectstatic --no-input
python3 start_server.py --reload || echo 'maybe you need to execute "python manage.py migrate" again?'
