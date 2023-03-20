import os

from google.cloud import pubsub_v1
from openbook_common.pubsub.helpers import mask_sensitive_values
import structlog

logger = structlog.getLogger(__name__)

GOOGLE_CLOUD_PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "holi-dev")


def publish_event(topic: str, event: dict) -> None:
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(GOOGLE_CLOUD_PROJECT_ID, topic)
    publisher.publish(topic_path, **event)
    logger.info(f"Event published {mask_sensitive_values(event)}")
