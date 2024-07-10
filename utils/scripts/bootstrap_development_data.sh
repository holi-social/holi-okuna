#!/bin/bash

echo "🗑 Clearing existing data"
python manage.py flush --noinput

# install pip env deps, run migrations, collect media, start the server

echo "👨‍🔧 Applying migrations"
python manage.py migrate

echo "👩‍💻 Loading development data"
python manage.py loaddata emoji-groups.json emojis.json badges.json categories.json languages.json topics.json skills.json sdgs.json moderation_categories.json feed_post_categories.json

echo "🖼  Copying development media"
cp -a utils/development_data/media .

echo "✅ All done"
