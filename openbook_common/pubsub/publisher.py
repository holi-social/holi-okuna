from google.cloud import pubsub_v1
from openbook import settings
import structlog

from openbook_common.pubsub.event import Event

logger = structlog.getLogger(__name__)

GOOGLE_CLOUD_PROJECT_ID = settings.GOOGLE_CLOUD_PROJECT_ID


def publish_event(topic: str, event: Event) -> None:
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(GOOGLE_CLOUD_PROJECT_ID, topic)
    publisher.publish(topic_path, **event.to_dict())
    logger.info(f"Event published {event.to_dict()}")
