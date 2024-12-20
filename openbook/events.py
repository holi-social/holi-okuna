import structlog

from openbook_auth.models import User
from openbook_common.pubsub.publisher import publish_event
from openbook_communities.events.events import (
    SpaceCreatedEvent,
    SpaceUpdatedEvent,
    SpaceDeletedEvent,
    SpaceUserAddedEvent,
    SpaceUserLeftEvent,
    SpaceUserRemovedEvent,
    UserDeletedEvent,
    UserNameUpdatedEvent,
    UserEmailUpdatedEvent,
)
from openbook_communities.events.payloads import SpacePayload, UserPayload
from openbook_communities.events.topic import Topic as PubSubTopic
from openbook_communities.models import Community

logger = structlog.getLogger(__name__)


def publish_space_created_event(community: Community):
    try:
        creator = UserPayload.from_user(community.creator)
        space = SpacePayload.from_community(community)
        event = SpaceCreatedEvent(creator, space)
        publish_event(event=event, topic=PubSubTopic.OKUNA.value)
    except Exception as e:
        logger.error("Failed to publish event: %s", str(e), exc_info=True)


def publish_space_updated_event(community: Community):
    try:
        creator = UserPayload.from_user(community.creator)
        space = SpacePayload.from_community(community)
        event = SpaceUpdatedEvent(creator, space)
        publish_event(event=event, topic=PubSubTopic.OKUNA.value)
    except Exception as e:
        logger.error("Failed to publish event: %s", str(e), exc_info=True)


def publish_space_user_added_event(username: str, community: Community):
    try:
        space_member: User = User.objects.get(username=username)
        user = UserPayload.from_user(space_member)
        space = SpacePayload.from_community(community)
        event = SpaceUserAddedEvent(user, space)
        publish_event(event=event, topic=PubSubTopic.OKUNA.value)
    except Exception as e:
        logger.error("Failed to publish event: %s", str(e), exc_info=True)


def publish_user_name_updated_event(user: User):
    try:
        updated_user = UserPayload.from_user(user)
        event = UserNameUpdatedEvent(updated_user)
        publish_event(event=event, topic=PubSubTopic.OKUNA.value)
    except Exception as e:
        logger.error("Failed to publish event: %s", str(e), exc_info=True)


def publish_user_email_updated_event(user: User):
    try:
        updated_user = UserPayload.from_user(user)
        event = UserEmailUpdatedEvent(updated_user)
        publish_event(event=event, topic=PubSubTopic.OKUNA.value)
    except Exception as e:
        logger.error("Failed to publish event: %s", str(e), exc_info=True)


def publish_space_deleted_event(community: Community):
    try:
        space = SpacePayload.from_community(community)
        event = SpaceDeletedEvent(space)
        publish_event(event=event, topic=PubSubTopic.OKUNA.value)
    except Exception as e:
        logger.error("Failed to publish event: %s", str(e), exc_info=True)


def publish_user_deleted_event(user: User):
    try:
        deleted_user = UserPayload.from_user(user)
        event = UserDeletedEvent(deleted_user)
        publish_event(event=event, topic=PubSubTopic.OKUNA.value)
    except Exception as e:
        logger.error("Failed to publish event: %s", str(e), exc_info=True)


def publish_space_user_left_event(user: User, community: Community):
    try:
        user = UserPayload.from_user(user)
        space = SpacePayload.from_community(community)
        event = SpaceUserLeftEvent(user, space)
        publish_event(event=event, topic=PubSubTopic.OKUNA.value)
    except Exception as e:
        logger.error("Failed to publish event: %s", str(e), exc_info=True)


def publish_space_user_removed_event(user: User, community: Community):
    try:
        user = UserPayload.from_user(user)
        space = SpacePayload.from_community(community)
        event = SpaceUserRemovedEvent(user, space)
        publish_event(event=event, topic=PubSubTopic.OKUNA.value)
    except Exception as e:
        logger.error("Failed to publish event: %s", str(e), exc_info=True)
