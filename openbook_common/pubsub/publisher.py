import json

from google.cloud import pubsub_v1
from openbook import settings
from openbook_common.pubsub.helpers import mask_sensitive_values
import structlog

logger = structlog.getLogger(__name__)

GOOGLE_CLOUD_PROJECT_ID = settings.GOOGLE_CLOUD_PROJECT_ID


def publish_event(topic: str, event: dict) -> None:
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(GOOGLE_CLOUD_PROJECT_ID, topic)
    publisher.publish(topic_path, **event)
    event["data"] = json.loads(event["data"].decode())
    logger.info(f"Event published {mask_sensitive_values(event)}")
