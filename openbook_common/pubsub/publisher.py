from google.cloud import pubsub_v1
from google.auth.credentials import AnonymousCredentials
from openbook import settings
import structlog

from google.cloud.pubsub_v1.types import PublisherOptions

from openbook_common.pubsub.event import Event
from openbook_common.pubsub.wrappers import skip_test_events

logger = structlog.getLogger(__name__)

GOOGLE_CLOUD_PROJECT_ID = settings.GOOGLE_CLOUD_PROJECT_ID
ENVIRONMENT_ID = settings.ENVIRONMENT_ID

# subscribers can choose to consume messages in order. using a single ordering key because it gives the highest
# guarantees, and we currently don't have scale issues that would justify relaxing guarantees.
ORDERING_KEY = "okuna"


@skip_test_events
def publish_event(topic: str, event: Event) -> None:
    try:
        publisher_options = PublisherOptions(enable_message_ordering=True)
        publisher = (
            pubsub_v1.PublisherClient(credentials=AnonymousCredentials(), publisher_options=publisher_options)
            if ENVIRONMENT_ID == "local"
            else pubsub_v1.PublisherClient(publisher_options=publisher_options)
        )
        topic_path = publisher.topic_path(GOOGLE_CLOUD_PROJECT_ID, topic)
        publisher.publish(topic_path, ordering_key=ORDERING_KEY, **event.to_dict())
        logger.info(f"Event published {event.to_dict()}")
    except Exception as e:
        logger.error(
            f"Failed to publish event to topic {topic}. Make sure that the Google Cloud Pub/Sub API is enabled for your project and that the GOOGLE_APPLICATION_CREDENTIALS environment variable is set correctly.",
            str(e),
        )
