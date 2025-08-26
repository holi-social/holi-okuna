from dataclasses import dataclass
from typing import Dict, Any

from semver import Version


@dataclass
class IncomingEvent:
    event_type: str
    event_version: Version
    data: Dict[str, Any]

    @staticmethod
    def of(data: Dict[str, Any]):
        event_type = data.get("eventType")
        event_version = Version.parse(data.get("eventVersion"))
        data = data.get("data")
        if not (event_type and event_version and data):
            raise ValueError(f"Missing essentials of events in data: {data}")
        return IncomingEvent(event_type, event_version, data)

    def __str__(self) -> str:
        return f"IncomingEvent(event_type={self.event_type}, event_version={self.event_version})"
