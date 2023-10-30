import logging
from functools import wraps

from openbook_common.enums import FeatureToggleName, FeatureToggleType
from openbook_common.models import FeatureToggle as FeatureToggleModel

logger = logging.getLogger(__name__)


def notifications_toggle(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            notifications_feature_toggle = FeatureToggleModel.objects.get(name=FeatureToggleName.NOTIFICATIONS.value)
            if notifications_feature_toggle.status == FeatureToggleType.PRODUCTION:
                return func(*args, **kwargs)
        except FeatureToggleModel.DoesNotExist:
            logger.warning(f"Feature toggle {FeatureToggleName.NOTIFICATIONS.value} does not exist")
            pass

    return wrapper


def mute_notifications(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            notifications_feature_toggle = FeatureToggleModel.objects.get(name=FeatureToggleName.NOTIFICATIONS.value)
            if notifications_feature_toggle.status == FeatureToggleType.PRODUCTION:
                return
        except FeatureToggleModel.DoesNotExist:
            logger.warning(f"Feature toggle {FeatureToggleName.NOTIFICATIONS.value} does not exist")
        return func(*args, **kwargs)

    return wrapper
