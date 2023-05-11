from openbook_common.pubsub.event import Event
from functools import wraps
from openbook import settings

ENVIRONMENT_ID = settings.ENVIRONMENT_ID


def skip_test_events(func):
    @wraps(func)
    def wrapper(topic: str, event: Event) -> None:
        user_email = event.data.get("user", {}).get("email", "")
        space_name = event.data.get("space", {}).get("name", "")

        if ENVIRONMENT_ID == "staging" and (user_email.endswith("@e2etest.com") or space_name.startswith("e2e")):
            return  # Skip publishing the event

        return func(topic, event)

    return wrapper
