#!/bin/bash
set -eo pipefail

/wait-for-it.sh $RDS_HOSTNAME:$RDS_PORT -t 60

/wait-for-it.sh $REDIS_HOST:$REDIS_PORT -t 60

cd /opt/okuna-api

python manage.py migrate
python manage.py loaddata emoji-groups.json emojis.json badges.json categories.json languages.json topics.json skills.json sdgs.json moderation_categories.json feed_post_categories.json
# remove stale content types on boot in all envs (remove after release 1.59 has successfully deployed)
python manage.py remove_stale_contenttypes --noinput