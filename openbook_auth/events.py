from enum import Enum
from typing import Optional

import structlog
from openbook_auth.models import User
from openbook_common.pubsub.event import Event
from openbook_common.pubsub.topic import Topic
from openbook_common.pubsub.publisher import publish_event

logger = structlog.getLogger(__name__)


class UserPayload:
    def __init__(
        self,
        id: str,
        name: str,
        email: str,
        identity: str,
        avatar: Optional[str] = None,
        about_me: Optional[str] = None,
        location: Optional[str] = None,
    ):
        self.id = id
        self.name = name
        self.email = email
        self.identity = identity
        self.avatar = avatar
        self.about_me = about_me
        self.location = location

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "identity": self.identity,
            "avatar": self.avatar,
            "aboutMe": self.about_me,
            "location": self.location,
        }

    @classmethod
    def from_user(cls, user: User):
        avatar_url = user.profile.avatar.url if user.profile.avatar else None
        return cls(
            id=str(user.username),
            name=user.profile.full_name(),
            email=user.email,
            identity=user.identity,
            avatar=avatar_url,
            about_me=user.profile.about_me,
            location=user.profile.location,
        )


class UserEventType(Enum):
    USER_NAME_UPDATED = "UserNameUpdated"
    USER_EMAIL_UPDATED = "UserEmailUpdated"
    USER_DELETED = "UserDeleted"


class UserNameUpdatedEvent(Event):
    EVENT_VERSION = "1.1.0"

    def __init__(self, user: UserPayload):
        super().__init__(
            data={"user": user.to_dict()},
            event_type=UserEventType.USER_NAME_UPDATED.value,
            event_version=UserNameUpdatedEvent.EVENT_VERSION,
        )


class UserEmailUpdatedEvent(Event):
    EVENT_VERSION = "1.1.0"

    def __init__(self, user: UserPayload):
        super().__init__(
            data={"user": user.to_dict()},
            event_type=UserEventType.USER_EMAIL_UPDATED.value,
            event_version=UserEmailUpdatedEvent.EVENT_VERSION,
        )


class UserDeletedEvent(Event):
    EVENT_VERSION = "1.1.0"

    def __init__(self, user: UserPayload):
        super().__init__(
            data={"user": user.to_dict()},
            event_type=UserEventType.USER_DELETED.value,
            event_version=UserDeletedEvent.EVENT_VERSION,
        )


def publish_user_deleted_event(user: User):
    deleted_user = UserPayload.from_user(user)
    event = UserDeletedEvent(deleted_user)
    publish_event(event=event, topic=Topic.OKUNA.value)


def publish_user_name_updated_event(user: User):
    updated_user = UserPayload.from_user(user)
    event = UserNameUpdatedEvent(updated_user)
    publish_event(event=event, topic=Topic.OKUNA.value)


def publish_user_email_updated_event(user: User):
    updated_user = UserPayload.from_user(user)
    event = UserEmailUpdatedEvent(updated_user)
    publish_event(event=event, topic=Topic.OKUNA.value)
