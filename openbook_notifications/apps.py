import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class OpenbookNotificationsConfig(AppConfig):
    name = "openbook_notifications"
