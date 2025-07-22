from dataclasses import dataclass

import structlog

from openbook_common.pubsub.incoming_event import IncomingEvent

logger = structlog.get_logger(__name__)


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
