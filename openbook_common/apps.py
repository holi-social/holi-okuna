from django.apps import AppConfig

from openbook.settings import POSTHOG_API_KEY, POSTHOG_HOST
from openbook_common.tracking import initialize_tracking, PostHogConfig


class OpenbookCommonConfig(AppConfig):
    name = "openbook_common"

    def ready(self):
        initialize_tracking(PostHogConfig(api_key=POSTHOG_API_KEY, host=POSTHOG_HOST, disable_for_testing=False))
