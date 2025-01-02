from google.cloud import pubsub_v1
from google.auth.credentials import AnonymousCredentials
from openbook import settings
import structlog

from openbook_common.pubsub.event import Event
from openbook_common.pubsub.wrappers import skip_test_events

logger = structlog.getLogger(__name__)

GOOGLE_CLOUD_PROJECT_ID = settings.GOOGLE_CLOUD_PROJECT_ID
ENVIRONMENT_ID = settings.ENVIRONMENT_ID
PUBLISH_TIMEOUT_SECONDS = 15


@skip_test_events
def publish_event(topic: str, event: Event) -> None:
    """
    Publishes an event to Google Cloud Pub/Sub. Guaranteed to not throw.
    Awaits the result of the publish operation and logs any errors.
    """
    try:
        publisher = (
            pubsub_v1.PublisherClient(credentials=AnonymousCredentials())
            if ENVIRONMENT_ID == "local"
            else pubsub_v1.PublisherClient()
        )
        topic_path = publisher.topic_path(GOOGLE_CLOUD_PROJECT_ID, topic)
        future = publisher.publish(topic_path, **event.to_dict())

        try:
            future.result(PUBLISH_TIMEOUT_SECONDS)
        except Exception as publish_error:
            logger.error(_publish_error_msg(event, publish_error))

    except Exception as setup_error:
        # Handle general errors in the publishing setup or process
        logger.error(_publish_error_msg(event, setup_error))


def _publish_error_msg(event: Event, e: Exception) -> str:
    return f"Failed to publish {type(event).__name__} event. Ensure Google Cloud Pub/Sub is enabled and GOOGLE_APPLICATION_CREDENTIALS is set correctly. Exception: {str(e)}"
