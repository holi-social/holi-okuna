from dataclasses import dataclass
from typing import Dict, Any

import structlog

from semver import Version

from favorites.models import UserFavorite

logger = structlog.get_logger(__name__)


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


@dataclass
class VolunteeringDeletedEvent(IncomingEvent):
    record_id: str

    @staticmethod
    def of(incoming_event: IncomingEvent):
        record_id = incoming_event.data.get("id")
        if record_id:
            return VolunteeringDeletedEvent(
                incoming_event.event_type, incoming_event.event_version, incoming_event.data, record_id
            )
        else:
            raise ValueError(f"Missing record_id in event data: {incoming_event.data}")


class ExternalDataEventHandler:
    @staticmethod
    def handle(incoming_event: IncomingEvent):
        if "VolunteeringDeleted" == incoming_event.event_type:
            logger.info("Processing VolunteeringDeleted event")
            event = VolunteeringDeletedEvent.of(incoming_event)
            UserFavorite.delete_all_favorites_for_external_volunteering_opportunity(event.record_id)
            return True

        logger.warning(f"Ignoring unhandled event type: {incoming_event.event_type}")
        return True
