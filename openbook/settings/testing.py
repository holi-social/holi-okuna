from . import *

ENVIRONMENT = EnvironmentChecker.TEST_VALUE
TESTING = True

for queueConfig in RQ_QUEUES.values():
    queueConfig["ASYNC"] = False

TEST_DB_NAME = os.environ.get("TEST_DB_NAME", "okuna_test_db")
TEST_DB_USERNAME = os.environ.get("TEST_DB_USERNAME", "okuna_test_user")
TEST_DB_PASSWORD = os.environ.get("TEST_DB_PASSWORD", "okuna_test_password")
TEST_DB_HOSTNAME = os.environ.get("TEST_DB_HOSTNAME", "postgres")
TEST_DB_PORT = os.environ.get("TEST_DB_PORT")

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

DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

APPLE_APP_STORE_DEFAULT_URL = "itms-apps://apps.apple.com/app/HOLITEST"
GOOGLE_PLAY_STORE_DEFAULT_URL = "market://details?id=foundation.holistic.HOLITEST"
