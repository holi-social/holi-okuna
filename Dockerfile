FROM python:3.11.0

RUN apt-get -y update && apt-get -y upgrade && apt-get install -y ffmpeg

COPY requirements.txt /requirements.txt

RUN pip install --upgrade pip
RUN pip install -r /requirements.txt

COPY . /opt/okuna-api

# Copy any files over
COPY .docker/api/wait-for-it.sh /wait-for-it.sh
COPY .docker/api/entrypoint.sh /entrypoint.sh
#COPY .docker/api/bootstrap_development_data.sh /bootstrap_development_data.sh

# Change permissions
RUN chmod +x /entrypoint.sh
#RUN chmod +x /bootstrap_development_data.sh
RUN chmod +x /wait-for-it.sh

WORKDIR /opt/okuna-api
# SECRET_KEY must be set, but the value is never used
run ENVIRONMENT=build SECRET_KEY=foo python manage.py collectstatic --no-input

ENTRYPOINT ["/entrypoint.sh"]

EXPOSE 80

#CMD ["python", "manage.py", "runserver", "0.0.0.0:80"]
CMD ["uvicorn", "openbook.asgi:application", "--host", "0.0.0.0", "--port", "80"]
