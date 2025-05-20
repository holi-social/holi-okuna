#!/bin/bash
set -eo pipefail

cd /opt/okuna-api

# prepare static files
#python manage.py collectstatic
# we most probably currently don't need to execute collectmedia, it only uploads emoji files.
#echo "yes" | python manage.py collectmedia # it always asks even if media folder is nonexistent

exec "$@"
