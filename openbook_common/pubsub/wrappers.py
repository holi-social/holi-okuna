from openbook_common.pubsub.event import Event
from functools import wraps


def skip_test_events(func):
    @wraps(func)
    def wrapper(topic: str, event: Event) -> None:
        user_email = event.data.get("user", {}).get("email", "")
        space_name = event.data.get("space", {}).get("name", "")

        if user_email.endswith("@e2etest.com") or space_name.startswith("e2e space"):
            return  # Skip publishing the event

        return func(topic, event)

    return wrapper
