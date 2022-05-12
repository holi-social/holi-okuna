FROM python:3.9.12

RUN apt-get -y update && apt-get -y upgrade &&  apt-get install -y ffmpeg

# Copy any files over
COPY wait-for-it.sh /wait-for-it.sh
COPY entrypoint.sh /entrypoint.sh
COPY bootstrap_development_data.sh /bootstrap_development_data.sh

# Change permissions
RUN chmod +x /entrypoint.sh
RUN chmod +x /bootstrap_development_data.sh
RUN chmod +x /wait-for-it.sh

ENTRYPOINT ["/entrypoint.sh"]

COPY ../../requirements.txt /requirements.txt

RUN pip install --upgrade pip
RUN pip install -r /requirements.txt

# fix for django_media_fixtures: Django removed django.utils.encoding.smart_text alias in Django 4.0
# see also https://github.com/adrianoveiga/django-media-fixtures/pull/6
RUN sed -i -e 's/smart_text/smart_str/g' /usr/local/lib/python3.9/site-packages/django_media_fixtures/management/commands/collectmedia.py

VOLUME ["/opt/okuna-api"]

EXPOSE 80

CMD ["python", "manage.py", "runserver", "0.0.0.0:80"]
