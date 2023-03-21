from enum import Enum

from openbook_common.pubsub.event import Event
from openbook_communities.events.payloads import SpacePayload, UserPayload


class EventType(Enum):
    SPACE_CREATED = "SpaceCreated"


class SpaceCreatedEvent(Event):
    EVENT_VERSION = "1.0.0"

    def __init__(self, user: UserPayload, space: SpacePayload):
        super().__init__(
            data={"user": user.to_dict(), "space": space.to_dict()},
            event_type=EventType.SPACE_CREATED.value,
            event_version=SpaceCreatedEvent.EVENT_VERSION,
        )
