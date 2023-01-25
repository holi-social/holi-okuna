# holi-okuna

The Okuna-based backend for HOLI.

## Table of contents

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Quickstart](#quickstart)
- [Changes to reduce dependencies](#changes-to-reduce-dependencies)
  - [spectra==0.0.11](#spectra0011)
  - [colormath==3.0.0](#colormath300)
- [Known installation issues](#known-installation-issues)
  - [MacOs](#macos)
- [CI/CD](#cicd)

## Introduction

holi-okuna is based on / forked off okuna-api, the backend of the Okuna project. See `README_OKUNA.md` for the
original (more extensive) README. This README here is thought for a quickstart and gives additional information about
specifics of the HOLI project.

## Prerequisites

The project uses

- Python 3.11+
- Django 4
- PostgreSQL
- Redis
- `docker` / `docker-compose`
- [pyenv](https://github.com/pyenv/pyenv) (optional)
- [Black code formatter](https://github.com/psf/black) (see the [docs](https://black.readthedocs.io/en/stable/) for IDE integrations)

## Quickstart
If you have installed pyenv, you can execute `./reset_environment.sh` to install the required python interpreter,
set up the virtual environment and install the required dependencies.

Start the required services using `python okuna-cli.py up-services-only`

Start the dev server using `python manage.py runserver 0.0.0.0:8000`
### Reset
Use `python okuna-cli.py clean` to reset all local state, including database and config files.

### Step by step

1. Make sure you're actually running the correct Python version (see .python-version file) by running `python --version`, if you
   are using pyenv, the version check will be executed implicitly for you.

   Use `pyenv install $PYENV_VERSION` to install the currently used interpreter and delete your `.venv` folder to remove
   the deprecated environment.

2. Install AND **set up** [`direnv`](http://direnv.net) and run `direnv allow .` in the current directory in order for
   `direnv` to initialise the development environment (variables). This should automatically create a Python 3 venv,
   load the environment and set some environment variables (see `.envrc` for details).

3. Run

   ```sh
   pip install -r requirements.txt
   pip install -r requirements-cli-only.txt
   python okuna-cli.py up-services-only
   ```

   This starts up docker-compose with the following processes:

   - scheduler
   - worker
   - db
   - redis

   Then, run all the database migrations

   ```sh
   python manage.py migrate
   ```

   And fill the DB with some fixture data:

   ```bash
   python manage.py loaddata circles.json emoji-groups.json emojis.json badges.json categories.json languages.json topics.json skills.json sdgs.json moderation_categories.json users.json
   ```

   Afterwards, you're ready to start the backend API service:

   ```sh
   python start_server.py # this binds to http://127.0.0.1:8000
   
   #should you need more control you can also use:
   uvicorn openbook.asgi:application --reload [...more uvicorn options, like --host or --port...]
   ```
   
   Alternatively you can also start the Django development server, but then file uploads don't work:

   ```sh
   python manage.py runserver localhost:8000
   ```

   (or use `python manage.py runserver 0.0.0.0:8000` to bind to all interfaces)

**Please always use python okuna-cli.py instead of docker-compose directly!**

**Why?** okuna-cli.py creates a set of environment files (`.okuna-cli.json`, `.docker-compose.env` and `.env`). Those
files contain randomly generated passwords for db and redis and the like to be used by the started processes. Also, it
cleans up stuff on shutdown (docker networks & volumes, etc.), runs migrations and populates the db. **If you use
docker-compose directly you can easily get into inconsistent states and processes can’t talk to each other due to wrong
passwords and database contents etc!**

## Changes to reduce dependencies

### spectra==0.0.11

spectra has a dependency on numpy which takes very to load and compile. It is used in
`openbook_hashtags/management/commands/update_hashtags/luminance.py` to change the color of a hashtag.
It is also used in `openbook_common/utils/helpers.py` to darken a color.
Since we may not use these features, the spectra import and dependency was removed.

### colormath==3.0.0

colormath has a dependency on numpy and cannot be found via search in the source code.

## Known installation issues

### MacOs

Libmagic is not found on your mac? Try this command.

```sh
brew install libmagic
```

Xcode issues - Error: python@3.9: the bottle needs  the Apple Command Line Tools to be installed.

```sh
 xcode-select --install
 ```

ffpmeg is missing?

```sh
brew install ffmpeg 
```

## CI/CD

The CI/CD pipeline follows our normal flow, deploying branch environments and deploying main to staging automatically
and to production manually. The e2e tests that should go in between staging and prod deployments are missing up until now.

## Access local db

See `.env` for `RDS_USERNAME` and `RDS_PASSWORD`

```sh
psql -h localhost okuna -U <RDS_USERNAME>
```

## Admin Dashboard
When using a local database, first execute `python manage.py createsuperuser` to create an admin account with your
desired credentials.
If you are connected to the staging database, use the credentials found in [Passbolt](https://cloud.passbolt.com/holi/app/passwords)

After starting Okuna, you can access the admin ui at `http://localhost:8000/admin/`

## Pycharm
Shared run configurations can be found in the `.run` subfolder.
You can use these to start your dev server or run tests.
