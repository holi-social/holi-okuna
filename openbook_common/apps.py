from django.apps import AppConfig

from openbook_common.tracking import initialize_tracking


class OpenbookCommonConfig(AppConfig):
    name = "openbook_common"

    def ready(self):
        initialize_tracking()
