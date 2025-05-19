#!/bin/bash

# This file is used by the mprocs yaml files in https://gitlab.holi.team/app/holi-meta 

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
