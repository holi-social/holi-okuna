from . import *  # noqa: F403

ENVIRONMENT = EnvironmentChecker.TEST_VALUE  # noqa: F405
TESTING = True

for queue_config in RQ_QUEUES.values():  # noqa: F405, N816
    queue_config["ASYNC"] = False

TEST_DB_NAME = os.environ.get("TEST_DB_NAME", "okuna_test_db")  # noqa: F405
TEST_DB_USERNAME = os.environ.get("TEST_DB_USERNAME", "okuna_test_user")  # noqa: F405
TEST_DB_PASSWORD = os.environ.get("TEST_DB_PASSWORD", "okuna_test_password")  # noqa: F405
TEST_DB_HOSTNAME = os.environ.get("TEST_DB_HOSTNAME", "postgres")  # noqa: F405
TEST_DB_PORT = os.environ.get("TEST_DB_PORT")  # noqa: F405

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": TEST_DB_NAME,
        "USER": TEST_DB_USERNAME,
        "PASSWORD": TEST_DB_PASSWORD,
        "HOST": TEST_DB_HOSTNAME,
        "PORT": TEST_DB_PORT,
    }
}

OS_TRANSLATION_STRATEGY_NAME = "testing"
MIN_UNIQUE_TOP_POST_REACTIONS_COUNT = 1
MIN_UNIQUE_TOP_POST_COMMENTS_COUNT = 1
MIN_UNIQUE_TRENDING_POST_REACTIONS_COUNT = 1

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

APPLE_APP_STORE_DEFAULT_URL = "itms-apps://apps.apple.com/app/HOLITEST"
GOOGLE_PLAY_STORE_DEFAULT_URL = "market://details?id=foundation.holistic.HOLITEST"


# speed up pytest by not running migrations
# see https://stackoverflow.com/questions/36487961/django-unit-testing-taking-a-very-long-time-to-create-test-database
class DisableMigrations(object):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()
