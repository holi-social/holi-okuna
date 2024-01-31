# holi-okuna

The Okuna-based backend for HOLI.

## Table of contents

<!-- TOC -->
- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
  - [Geospatial libraries](#geospatial-libraries)
- [Quickstart](#quickstart)
  - [Reset](#reset)
  - [Step by step](#step-by-step)
- [Changes to reduce dependencies](#changes-to-reduce-dependencies)
  - [spectra==0.0.11](#spectra0011)
  - [colormath==3.0.0](#colormath300)
- [Known installation issues](#known-installation-issues)
  - [MacOs](#macos)
- [CI/CD](#cicd)
- [Access local db](#access-local-db)
- [Admin Dashboard](#admin-dashboard)
- [Pycharm](#pycharm)
- [Services using email](#email-and-smtp-configuration)
- [Translations](#translations)
- [Tests](#tests)
<!-- /TOC -->

## Introduction

holi-okuna is based on / forked off okuna-api, the backend of the Okuna project. See `README_OKUNA.md` for the
original (more extensive) README. This README here is thought for a quickstart and gives additional information about
specifics of the HOLI project.

## Prerequisites

The project uses

- Python 3.10+
- Django 4
- PostgreSQL (with [PostGIS](https://postgis.net/) extension)
- Redis
- `docker` / `docker-compose`
- [pyenv](https://github.com/pyenv/pyenv) (optional)
- [Black code formatter](https://github.com/psf/black) (see the [docs](https://black.readthedocs.io/en/stable/) for IDE integrations)

### Geospatial libraries

The following geospatial libraries should be installed prior to building PostGIS.

- [GEOS](https://libgeos.org/)
- [PROJ](https://proj.org/)
- [GDAL](https://gdal.org/)

You should also update your local `.env` and `.docker-compose.env` to include the geospatial libraries paths in your local machine.

```
GDAL_LIBRARY_PATH = "/path/to/libgdal.dylib"
GEOS_LIBRARY_PATH = "/path/to/libgeos_c.dylib"
PROJ_LIBRARY_PATH = "/path/to/libproj.dylib"
```

On Mac you can use

```
brew install gdal proj geos
```

and

```
GDAL_LIBRARY_PATH = "/opt/homebrew/lib/libgdal.dylib"
GEOS_LIBRARY_PATH = "/opt/homebrew/lib/libgeos_c.dylib"
PROJ_LIBRARY_PATH = "/opt/homebrew/lib/libproj.dylib"
```

## Quickstart

If you have installed pyenv, you can execute `./reset_environment.sh` to install the required python interpreter,
set up the virtual environment and install the required dependencies.

Start the required services using `python3 okuna-cli.py up-services-only`

Start the dev server using `python3 start_server.py --reload`

### Reset

Use `python3 okuna-cli.py clean` to reset all local state, including database and config files.

### Step by step

1. Make sure you're actually running the correct Python version (see .python-version file) by running `python3 --version`, if you
   are using pyenv, the version check will be executed implicitly for you.

   Use `pyenv install $PYENV_VERSION` to install the currently used interpreter and delete your `.venv` folder to remove
   the deprecated environment. `reset_environment.sh` does what you need.

2. Install AND **set up** [`direnv`](http://direnv.net) and run `direnv allow .` in the current directory in order for
   `direnv` to initialise the development environment (variables). This should automatically create a Python 3 venv,
   load the environment and set some environment variables (see `.envrc` for details).

3. Run

   ```sh
   pip install -r requirements.txt
   pip install -r requirements-cli-only.txt
   python3 okuna-cli.py up-services-only
   ```

   This starts up docker-compose with the following processes:

   - scheduler
   - worker
   - db
   - redis

   \
   You now need to fill some values in the created `.env` file.
   In particular, you need to fill all values that are left empty.\
   If you are on an ARM Mac, you should also uncomment the POSTGRES_IMAGE entry.\
   \
   Then, run all the database migrations

   ```sh
   python3 manage.py migrate
   ```

   And fill the DB with some fixture data:

   ```bash
   python3 manage.py loaddata emoji-groups.json emojis.json badges.json categories.json languages.json topics.json skills.json sdgs.json inspirationpostcategories.json moderation_categories.json
   ```

   In addition, there is also a users.json you can load, if you want.

   You can generate more test data with a custom command:

   ```bash
   python3 manage.py generate_dummy_data --user 20 --post 10 --post_with_comment 20 --post_with_comment_and_reaction 20 --insight 10
   ```

   All parameters are optional.
   Users for posts, comments and insights are chosen at random.
   Insights get some random posts assigned as well.

   Afterwards, you're ready to start the backend API service:

   ```sh
   python3 start_server.py # this binds to http://127.0.0.1:8000

   #should you need more control you can also use:
   uvicorn openbook.asgi:application --reload [...more uvicorn options, like --host or --port...]
   ```

   Alternatively you can also start the Django development server, but this is discouraged and then file uploads don't work:

   ```sh
   python3 manage.py runserver localhost:8000
   ```

   (or use `python3 manage.py runserver 0.0.0.0:8000` to bind to all interfaces)

**Please always use python3 okuna-cli.py instead of docker-compose directly!**

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

If the error still persists, libmagic might be [installed under a different path](http://www.brambraakman.com/blog/comments/installing_libmagic_in_mac_os_x_for_python-magic/), e.g. `/opt/homebrew/Cellar/libmagic`.

Run `brew link libmagic` to find out the correct path and create a symbolic link, e.g.

```sh
cd /usr/local/lib/
ln -s <correct path>/lib/libmagic.dylib libmagic.dylib
```

Xcode issues - Error: python@3.9: the bottle needs the Apple Command Line Tools to be installed.

```sh
 xcode-select --install
```

## CI/CD

The CI/CD pipeline follows our normal flow, deploying branch environments and deploying main to staging automatically
and to production manually. The e2e tests that should go in between staging and prod deployments are missing up until
now.

## Access local db

See `.env` for `RDS_USERNAME` and `RDS_PASSWORD`

```sh
psql -h localhost okuna -U <RDS_USERNAME>
```

## Admin Dashboard

When using a local database, first execute `python3 manage.py createsuperuser` to create an admin account with your
desired credentials.
If you are connected to the staging database, use the credentials found
in [Passbolt](https://cloud.passbolt.com/holi/app/passwords)

After starting Okuna, you can access the admin ui at `http://localhost:8000/admin/`

## Pycharm

Shared run configurations can be found in the `.run` subfolder.
You can use these to start your dev server or run tests.

## Email and SMTP configuration

For emails we use Django's django.core.mail.backends.smtp.EmailBackend library and in order to have it work you need to set the following env variables:

```
EMAIL_HOST
EMAIL_HOST_PASSWORD
EMAIL_HOST_USER
DEFAULT_FROM_EMAIL
SERVER_EMAIL
SERVICE_EMAIL_ADDRESS
```

## Translations

Django offers translation utility hooks out of the box. For us at **holi**, these are useful to display localized response
messages to the Front-end. These "hooks" are called translation strings, and they store the extracted translation
strings into a message file with the `.po` extension.

```python
   # Translation Strings
_("Welcome holis")
```

You must generate new translations whenever you update or include a new response message using translation strings,
including `raise` messages. This can be done in your terminal

```sh
   ./manage.py makemessages --all --no-wrap
   ./manage.py compilemessages
```

## Tests

We are using `pytest` for test execution and can run the tests the following way:

```sh
pytest
# Execute a single test file
pytest openbook/tests/test_graphql.py
# Execute a single test case
pytest -k "test_correctly_updates_onboarding_steps"
```
