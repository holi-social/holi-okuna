import logging
from functools import wraps

from openbook.settings import TESTING, IS_BUILD

logger = logging.getLogger(__name__)


# Functions annotated with mute_notifications will never be executed in production. This decorator was introduced
# to be used in the context of migrating individual notification types from the Okuna-based Notification system
# to Novu. Once the old system is removed, this decorator and code using it can also be removed.
def mute_notifications(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # As long as the old Okuna-based subsystem is not removed, some tests still rely on the code being executed.
        if TESTING or IS_BUILD:
            return func(*args, **kwargs)
        else:
            return

    return wrapper
