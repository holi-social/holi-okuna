#!/bin/bash

echo "🗑 Clearing existing data"
python manage.py reset_db --noinput

# install pip env deps, run migrations, collect media, start the server

echo "👨‍🔧 Applying migrations"
python manage.py migrate

echo "👩‍💻 Loading development data"
python manage.py loaddata circles.json emoji-groups.json emojis.json badges.json categories.json languages.json users.json

echo "🖼  Copying development media"
cp -a utils/development_data/media .

echo "✅ All done"
