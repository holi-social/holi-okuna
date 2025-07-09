from typing import Dict, Any

import structlog

from favorites.models import UserFavorite

logger = structlog.get_logger(__name__)


class ExternalDataEvent:
    def __init__(self, event_type: str, event_version: str, data: Dict[str, Any]):
        self.event_type = event_type
        self.event_version = event_version
        self.data = data

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eventType": self.event_type,
            "eventVersion": self.event_version,
            "data": self.data,
        }


class VolunteeringDeletedEvent(ExternalDataEvent):
    def __init__(self, record_id: str):
        super().__init__(
            event_type="VolunteeringDeleted",
            event_version="1.0.0",
            data={"id": record_id},
        )


class ExternalDataEventHandler:
    @staticmethod
    def handle_event(event_data: Dict[str, Any]) -> bool:
        try:
            event_type = event_data.get("eventType")

            if event_type == "VolunteeringDeleted":
                record_id = event_data.get("data", {}).get("id")
                if record_id:
                    logger.info(f"Processing VolunteeringDeleted event for record_id: {record_id}")
                    UserFavorite.delete_all_favorites_for_external_volunteering_opportunity(record_id)
                    return True
                else:
                    logger.error("Missing record_id in VolunteeringDeleted event")
            else:
                logger.info(f"Unhandled event type: {event_type}")

            return False
        except Exception as e:
            logger.error(f"Error handling external data event: {e}")
            return False
