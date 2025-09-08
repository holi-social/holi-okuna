import structlog
from openbook_auth.models import User, UserProfile
from openbook_common.pubsub.event import Event
from openbook_common.pubsub.topic import Topic
from openbook_common.pubsub.publisher import publish_event

logger = structlog.getLogger(__name__)


def user_to_event_payload(user):
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = None
    return {
        "id": str(user.username),
        "name": profile.full_name() if profile else None,
        "email": user.email,
        "identity": user.identity,
        "avatar": profile.avatar.url if profile and profile.avatar else None,
        "aboutMe": profile.about_me if profile else None,
        "location": profile.location if profile else None,
    }


class UserUpdatedEvent(Event):
    def __init__(self, user: User):
        super().__init__(
            data={"user": user_to_event_payload(user)},
            event_type="UserUpdated",
            event_version="1.1.0",
        )

    def log_str(self) -> str:
        return f"UserUpdated(user_id={self.data['user']['id']})"


class UserNameUpdatedEvent(Event):
    def __init__(self, user: User):
        super().__init__(
            data={"user": user_to_event_payload(user)},
            event_type="UserNameUpdated",
            event_version="1.1.0",
        )

    def log_str(self) -> str:
        return f"UserNameUpdated(user_id={self.data['user']['id']})"


class UserEmailUpdatedEvent(Event):
    def __init__(self, user: User):
        super().__init__(
            data={"user": user_to_event_payload(user)},
            event_type="UserEmailUpdated",
            event_version="1.1.0",
        )

    def log_str(self) -> str:
        return f"UserEmailUpdated(user_id={self.data['user']['id']})"


class UserDeletedEvent(Event):
    def __init__(self, user: User):
        super().__init__(
            data={"user": user_to_event_payload(user)},
            event_type="UserDeleted",
            event_version="1.1.0",
        )

    def log_str(self) -> str:
        return f"UserDeleted(user_id={self.data['user']['id']})"


def publish_user_deleted_event(user: User):
    publish_event(event=UserDeletedEvent(user), topic=Topic.OKUNA.value)


def publish_user_name_updated_event(user: User):
    publish_event(event=UserNameUpdatedEvent(user), topic=Topic.OKUNA.value)


def publish_user_updated_event(user: User):
    publish_event(event=UserUpdatedEvent(user), topic=Topic.OKUNA.value)


def publish_user_email_updated_event(user: User):
    publish_event(event=UserEmailUpdatedEvent(user), topic=Topic.OKUNA.value)
