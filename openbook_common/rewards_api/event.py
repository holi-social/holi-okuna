import json
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class AsDict(Protocol):
    def as_dict(self) -> dict:
        pass


class EmptyPayload:
    def as_dict(self) -> dict:
        return {}


@dataclass
class Event[Data: AsDict]:
    user_id: UUID
    event_type: str
    data: Data

    def to_json(self) -> str:
        return json.dumps(
            {
                "userId": str(self.user_id),
                "eventType": self.event_type,
                "data": self.data.as_dict(),
            }
        )
