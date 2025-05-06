from functools import wraps
from django.conf import settings


def skip_e2e_notifications(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        for arg in list(args) + list(kwargs.values()):
            user_email = getattr(arg, "email", None)
            if isinstance(user_email, str) and user_email.endswith("@e2etest.com"):
                if settings.ENVIRONMENT_ID == "staging":
                    return  # Skip sending the notification
        return func(*args, **kwargs)

    return wrapper
