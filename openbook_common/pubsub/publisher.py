from google.cloud import pubsub_v1
from google.auth.credentials import AnonymousCredentials
from openbook import settings
import structlog

from google.cloud.pubsub_v1.types import PublisherOptions

from openbook_common.pubsub.event import Event

logger = structlog.getLogger(__name__)

GOOGLE_CLOUD_PROJECT_ID = settings.GOOGLE_CLOUD_PROJECT_ID
ENVIRONMENT_ID = settings.ENVIRONMENT_ID
PUBLISH_TIMEOUT_SECONDS = 15

# subscribers can choose to consume messages in order. using a single ordering key because it gives the highest
# guarantees, and we currently don't have scale issues that would justify relaxing guarantees.
ORDERING_KEY = "okuna"


def publish_event(topic: str, event: Event) -> None:
    """
    Publishes an event to Google Cloud Pub/Sub. Guaranteed to not throw.
    Awaits the result of the publish operation and logs any errors.
    """
    try:
        publisher_options = PublisherOptions(enable_message_ordering=True)
        publisher = (
            pubsub_v1.PublisherClient(credentials=AnonymousCredentials(), publisher_options=publisher_options)
            if ENVIRONMENT_ID == "local"
            else pubsub_v1.PublisherClient(publisher_options=publisher_options)
        )
        topic_path = publisher.topic_path(GOOGLE_CLOUD_PROJECT_ID, topic)

        future = publisher.publish(
            topic=topic_path,
            data=event.encoded_data,
            ordering_key=ORDERING_KEY,
            # message.attributes:
            eventVersion=event.event_version,
            eventType=event.event_type,
            **event.additional_attributes,
        )

        try:
            future.result(PUBLISH_TIMEOUT_SECONDS)
            logger.info("Published event %s", event.log_str())
        except Exception as publish_error:
            logger.error(_publish_error_msg(event, publish_error))

    except Exception as setup_error:
        # Handle general errors in the publishing setup or process
        logger.error(_publish_error_msg(event, setup_error))


def _publish_error_msg(event: Event, e: Exception) -> str:
    return f"Failed to publish {type(event).__name__} event. Ensure Google Cloud Pub/Sub is enabled and authentication is set up correctly. Exception: {str(e)}"
