import json
from enum import Enum

from openbook_common.pubsub.payloads import Space, User


class EventType(Enum):
    SPACE_CREATED = "SpaceCreated"


class Event:
    def __init__(self, data: dict, event_type: str, event_version: str):
        self.data = data
        self.event_type = event_type
        self.event_version = event_version

    def to_dict(self) -> dict:
        return {
            "data": json.dumps(self.data).encode("utf-8"),
            "eventType": self.event_type,
            "eventVersion": self.event_version,
        }


class SpaceCreatedEvent(Event):
    EVENT_VERSION = "1.0.0"

    def __init__(self, user: User, space: Space):
        super().__init__(
            data={"user": user.to_dict(), "space": space.to_dict()},
            event_type=EventType.SPACE_CREATED.value,
            event_version=SpaceCreatedEvent.EVENT_VERSION,
        )
