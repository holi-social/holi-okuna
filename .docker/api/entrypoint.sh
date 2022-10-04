#!/bin/bash
set -euxo pipefail

/wait-for-it.sh $RDS_HOSTNAME:$RDS_PORT -t 60

/wait-for-it.sh $REDIS_HOST:$REDIS_PORT -t 60

cd /opt/okuna-api

# install pip env deps, run migrations, collect media, start the server
pip install -r requirements.txt --quiet

# prepare static files
yes yes | python manage.py collectstatic

python manage.py migrate
yes yes | python manage.py collectmedia
python manage.py loaddata circles.json emoji-groups.json emojis.json badges.json categories.json languages.json

exec $@
