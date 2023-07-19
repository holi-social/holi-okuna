from enum import Enum

from openbook_common.pubsub.event import Event
from openbook_communities.events.payloads import SpacePayload, UserPayload


class EventType(Enum):
    SPACE_CREATED = "SpaceCreated"
    SPACE_USER_ADDED = "SpaceUserAdded"
    USER_NAME_UPDATED = "UserNameUpdated"
    SPACE_DELETED = "SpaceDeleted"
    USER_DELETED = "UserDeleted"
    SPACE_USER_LEFT = "SpaceUserLeft"


class SpaceCreatedEvent(Event):
    EVENT_VERSION = "1.0.0"

    def __init__(self, creator: UserPayload, space: SpacePayload):
        super().__init__(
            data={"creator": creator.to_dict(), "space": space.to_dict()},
            event_type=EventType.SPACE_CREATED.value,
            event_version=SpaceCreatedEvent.EVENT_VERSION,
        )


class SpaceUserAddedEvent(Event):
    EVENT_VERSION = "1.0.0"

    def __init__(self, user: UserPayload, space: SpacePayload):
        super().__init__(
            data={"user": user.to_dict(), "space": space.to_dict()},
            event_type=EventType.SPACE_USER_ADDED.value,
            event_version=SpaceUserAddedEvent.EVENT_VERSION,
        )


class UserNameUpdatedEvent(Event):
    EVENT_VERSION = "1.0.0"

    def __init__(self, user: UserPayload):
        super().__init__(
            data={"user": user.to_dict()},
            event_type=EventType.USER_NAME_UPDATED.value,
            event_version=UserNameUpdatedEvent.EVENT_VERSION,
        )


class SpaceDeletedEvent(Event):
    EVENT_VERSION = "1.0.0"

    def __init__(self, space: SpacePayload):
        super().__init__(
            data={"space": space.to_dict()},
            event_type=EventType.SPACE_DELETED.value,
            event_version=SpaceDeletedEvent.EVENT_VERSION,
        )


class UserDeletedEvent(Event):
    EVENT_VERSION = "1.0.0"

    def __init__(self, user: UserPayload):
        super().__init__(
            data={"user": user.to_dict()},
            event_type=EventType.USER_DELETED.value,
            event_version=UserDeletedEvent.EVENT_VERSION,
        )


class SpaceUserLeftEvent(Event):
    EVENT_VERSION = "1.0.0"

    def __init__(self, user: UserPayload, space: SpacePayload):
        super().__init__(
            data={"user": user.to_dict(), "space": space.to_dict()},
            event_type=EventType.SPACE_USER_LEFT.value,
            event_version=SpaceUserLeftEvent.EVENT_VERSION,
        )
