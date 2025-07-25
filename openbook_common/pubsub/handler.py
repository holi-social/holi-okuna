from favorites.events import logger, VolunteeringDeletedEvent
from openbook_common.pubsub.incoming_event import IncomingEvent
from favorites.models import UserFavorite


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
