FROM python:3.11-slim

RUN apt-get -y update && \
    apt-get -y upgrade && \
    apt-get install -y \
        ffmpeg \
        binutils \
        libproj-dev \
        libgdal-dev \
        libgeos-dev && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Copy necessary scripts
COPY .docker/api/wait-for-it.sh .docker/api/entrypoint.sh .docker/api/migration-entrypoint.sh /
# Change permissions for scripts
RUN chmod +x /entrypoint.sh /wait-for-it.sh /migration-entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

COPY . /opt/okuna-api
WORKDIR /opt/okuna-api
#RUN pip install --no-cache-dir --upgrade pip && \
RUN pip install --no-cache-dir -r requirements.txt
RUN ENVIRONMENT=build SECRET_KEY=foo python manage.py collectstatic --no-input

EXPOSE 80
CMD ["python", "start_server.py", "--host", "0.0.0.0", "--port", "80"]
