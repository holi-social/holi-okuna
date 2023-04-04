import structlog
from openbook_auth.models import User
from openbook_common.pubsub.publisher import publish_event
from openbook_communities.events.events import SpaceCreatedEvent, SpaceUserAddedEvent, UserNameUpdatedEvent
from openbook_communities.events.payloads import SpacePayload, UserPayload
from openbook_communities.events.topic import Topic as PubSubTopic
from openbook_communities.models import Community

logger = structlog.getLogger(__name__)


def generate_publish_failure_message(cls):
    return f"Failed to publish {cls.__name__} event"


def publish_space_created_event(community: Community):
    try:
        creator = UserPayload.from_user(community.creator)
        space = SpacePayload.from_community(community)
        event = SpaceCreatedEvent(creator, space)
        publish_event(event=event, topic=PubSubTopic.OKUNA.value)
    except Exception as e:
        logger.error(generate_publish_failure_message(SpaceCreatedEvent), str(e))


def publish_space_user_added_event(username: str, community: Community):
    try:
        space_member: User = User.objects.get(username=username)
        user = UserPayload.from_user(space_member)
        space = SpacePayload.from_community(community)
        event = SpaceUserAddedEvent(user, space)
        publish_event(event=event, topic=PubSubTopic.OKUNA.value)
    except Exception as e:
        logger.error(generate_publish_failure_message(SpaceUserAddedEvent), str(e))


def publish_user_name_updated_event(user: User):
    try:
        updated_user = UserPayload.from_user(user)
        event = UserNameUpdatedEvent(updated_user)
        publish_event(event=event, topic=PubSubTopic.OKUNA.value)
    except Exception as e:
        logger.error(generate_publish_failure_message(UserNameUpdatedEvent), str(e))
