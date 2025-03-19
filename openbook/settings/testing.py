from . import *  # noqa: F403

ENVIRONMENT = EnvironmentChecker.TEST_VALUE  # noqa: F405
TESTING = True

for queue_config in RQ_QUEUES.values():  # noqa: F405, N816
    queue_config["ASYNC"] = False


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
