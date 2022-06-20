# holi-okuna

The Okuna-based backend for HOLI.

## Introduction
holi-okuna is based on / forked off okuna-api, the backend of the Okuna project. See `README_OKUNA.md` for the
original (more extensive) README. This README here is thought for a quickstart and gives additional information about
specifics of the HOLI project.

## Prerequisites
The project uses
* Python 3.9+
* Django 4
* PostgreSQL
* Redis
* `docker` / `docker-compose`

## Quickstart

1. Make sure you're actually running Python 3.9 or later by running `python --version`.
   
2. Install AND **set up** `direnv` (http://direnv.net) and run `direnv allow .` in the current directory in order for
   `direnv` to initialise the development environment (variables). This should automatically create a Python 3 venv,
   load the environment and set some environment variables (see `.envrc` for details).

3. Run
   ```
   pip install -r requirements.txt
   pip install -r requirements-cli-only.txt
   python okuna-cli.py up-services-only
   ```
   This starts up docker-compose with the following processes:
   
   * scheduler
   * worker
   * db
   * redis
   
   Then, run all the database migrations
   
   ```
   python manage.py migrate
   ```

   And fill the DB with some fixture data:

   ```bash
   python manage.py loaddata circles.json emoji-groups.json emojis.json badges.json categories.json languages.json
   ```
   
   Afterwards, you're ready to start the backend API service (in development mode):

   ```
   python manage.py runserver localhost:8000
   ```

   (or use `python manage.py runserver 0.0.0.0:8000` to bind to all interfaces)

**Please always use python okuna-cli.py instead of docker-compose directly!**

**Why?** okuna-cli.py creates a set of environment files (`.okuna-cli.json`, `.docker-compose.env` and `.env`). Those
files contain randomly generated passwords for db and redis and the like to be used by the started processes. Also, it
cleans up stuff on shutdown (docker networks & volumes, etc.), runs migrations and populates the db. **If you use
docker-compose directly you can easily get into inconsistent states and processes can’t talk to each other due to wrong
passwords and database contents etc!**


## How to generate a graphql endpoint via openapi
In order to generate the graphql schema, `drf-spectacular` and `openapi-to-graphql-cli` are needed. `drf-spectacular` is in 
the `requirements.txt`. In order to install `openapi-to-graphql-cli` run:
```
npm i -g openapi-to-graphql-cli
```

Generate the openapi schema via spectacular:
```
 ./manage.py spectacular --file schema.yml --api-version '0.0.63'
```
Inspect the schema.yml and maybe remove unneeded paths and actions and then run to generate the graphql schema:
```
openapi-to-graphql schema.yml --save schema.graphql
```

## Known installation issues

### MacOs

Libmagic is not found on your mac? Try this command.
```
brew install libmagic
```

Xcode issues - Error: python@3.9: the bottle needs  the Apple Command Line Tools to be installed.
```
 xcode-select --install
 ```

ffpmeg is missing?
```
brew install ffmpeg 
```
