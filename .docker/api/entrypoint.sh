#!/bin/bash
set -eo pipefail

/wait-for-it.sh $RDS_HOSTNAME:$RDS_PORT -t 60

/wait-for-it.sh $REDIS_HOST:$REDIS_PORT -t 60

cd /opt/okuna-api

# install pip env deps, run migrations, collect media, start the server
pip install -r requirements.txt --quiet

# prepare static files
python manage.py collectstatic

python manage.py migrate
echo "yes" | python manage.py collectmedia # it always asks even if media folder is nonexistent
python manage.py loaddata circles.json emoji-groups.json emojis.json badges.json categories.json languages.json

exec "$@"
