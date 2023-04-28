FROM python:3.11.3

RUN apt-get -y update && \
    apt-get -y upgrade && \
    apt-get install -y \
        ffmpeg \
        binutils \
        libproj-dev \
        libgdal-dev \
        libgeos-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /requirements.txt

RUN pip install --upgrade pip && \
    pip install --cache-dir=/root/.cache/pip -r /requirements.txt && \
    rm -rf /root/.cache/pip/*

COPY . /opt/okuna-api

# Copy any files over
COPY .docker/api/wait-for-it.sh .docker/api/entrypoint.sh /
#COPY .docker/api/bootstrap_development_data.sh /bootstrap_development_data.sh

# Change permissions
RUN chmod +x /entrypoint.sh
#RUN chmod +x /bootstrap_development_data.sh
RUN chmod +x /wait-for-it.sh

WORKDIR /opt/okuna-api
# SECRET_KEY must be set, but the value is never used
RUN ENVIRONMENT=build SECRET_KEY=foo python manage.py collectstatic --no-input

ENTRYPOINT ["/entrypoint.sh"]

EXPOSE 80

CMD ["python", "start_server.py", "--host", "0.0.0.0", "--port", "80"]
