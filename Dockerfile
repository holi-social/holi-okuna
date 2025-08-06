FROM europe-north1-docker.pkg.dev/holi-shared/docker-hub-remote/python:3.13.5-slim AS builder
COPY --from=europe-north1-docker.pkg.dev/holi-shared/ghcr-io-remote/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get -y update && \
    apt-get -y upgrade && \
    apt-get install -y \
        binutils \
        libproj-dev \
        libgdal-dev \
        libgeos-dev && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

FROM builder AS app_base_with_dependencies

ENV UV_INDEX_URL="https://europe-north1-python.pkg.dev/holi-shared/pypi-remote/simple/"
COPY pyproject.toml /opt/okuna-api/pyproject.toml
WORKDIR /opt/okuna-api
RUN --mount=type=cache,target=.uv-cache \
    export UV_LINK_MODE=copy && \
    uv export > requirements.txt && \
    uv pip install --system --compile-bytecode -r requirements.txt

FROM app_base_with_dependencies AS app

# Copy necessary scripts
COPY .docker/api/wait-for-it.sh .docker/api/entrypoint.sh .docker/api/migration-entrypoint.sh /
# Change permissions for scripts
RUN chmod +x /entrypoint.sh /wait-for-it.sh /migration-entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

COPY . /opt/okuna-api
WORKDIR /opt/okuna-api
RUN ENVIRONMENT=build SECRET_KEY=foo python manage.py collectstatic --no-input

EXPOSE 80
CMD ["python", "start_server.py", "--host", "0.0.0.0", "--port", "80"]
