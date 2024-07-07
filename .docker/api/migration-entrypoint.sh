#!/bin/bash
set -eo pipefail

/wait-for-it.sh $RDS_HOSTNAME:$RDS_PORT -t 60

/wait-for-it.sh $REDIS_HOST:$REDIS_PORT -t 60

cd /opt/okuna-api

python manage.py migrate
python manage.py loaddata emoji-groups.json emojis.json badges.json categories.json languages.json topics.json skills.json sdgs.json inspirationpostcategories.json moderation_categories.json feed_post_categories.json
