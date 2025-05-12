import structlog
from openbook_auth.models import User
from openbook_common.pubsub.event import Event
from openbook_common.pubsub.topic import Topic
from openbook_common.pubsub.publisher import publish_event

logger = structlog.getLogger(__name__)


def user_to_event_payload(user):
    return {
        "id": str(user.username),
        "name": user.profile.full_name(),
        "email": user.email,
        "identity": user.identity,
        "avatar": user.profile.avatar.url if user.profile.avatar else None,
        "aboutMe": user.profile.about_me,
        "location": user.profile.location,
    }


class UserUpdatedEvent(Event):
    def __init__(self, user: User):
        super().__init__(
            data={"user": user_to_event_payload(user)},
            event_type="UserUpdated",
            event_version="1.1.0",
        )


class UserNameUpdatedEvent(Event):
    def __init__(self, user: User):
        super().__init__(
            data={"user": user_to_event_payload(user)},
            event_type="UserNameUpdated",
            event_version="1.1.0",
        )


class UserEmailUpdatedEvent(Event):
    def __init__(self, user: User):
        super().__init__(
            data={"user": user_to_event_payload(user)},
            event_type="UserEmailUpdated",
            event_version="1.1.0",
        )


class UserDeletedEvent(Event):
    def __init__(self, user: User):
        super().__init__(
            data={"user": user_to_event_payload(user)},
            event_type="UserDeleted",
            event_version="1.1.0",
        )


def publish_user_deleted_event(user: User):
    publish_event(event=UserDeletedEvent(user), topic=Topic.OKUNA.value)


def publish_user_name_updated_event(user: User):
    publish_event(event=UserNameUpdatedEvent(user), topic=Topic.OKUNA.value)


def publish_user_updated_event(user: User):
    publish_event(event=UserUpdatedEvent(user), topic=Topic.OKUNA.value)


def publish_user_email_updated_event(user: User):
    publish_event(event=UserEmailUpdatedEvent(user), topic=Topic.OKUNA.value)
