from typing import Dict, Any

import structlog

from openbook_auth.events import user_to_event_payload
from openbook_auth.models import User
from openbook_common.pubsub.event import Event
from openbook_common.pubsub.publisher import publish_event
from openbook_common.pubsub.topic import Topic as PubSubTopic
from openbook_communities.models import Community, Task

logger = structlog.getLogger(__name__)


def space_to_event_payload(community):
    return {
        "id": str(community.id),
        "name": community.title,
        "slug": community.name,
        "avatar": community.avatar.url if community.avatar else None,
        "description": community.description,
        "location": community.location,
        "locationLatLng": {"latitude": community.geolocation.x, "longitude": community.geolocation.y}
        if community.geolocation
        else None,
        "topicsV2": community.topics_v2,
    }


class SpaceUserRemovedEvent(Event):
    def __init__(self, user: User, space: Community):
        super().__init__(
            data={"user": user_to_event_payload(user), "space": space_to_event_payload(space)},
            event_type="SpaceUserRemoved",
            event_version="1.2.0",
        )


class SpaceUserLeftEvent(Event):
    def __init__(self, user: User, space: Community):
        super().__init__(
            data={"user": user_to_event_payload(user), "space": space_to_event_payload(space)},
            event_type="SpaceUserLeft",
            event_version="1.2.0",
        )


class SpaceDeletedEvent(Event):
    def __init__(self, space: Community):
        super().__init__(
            data={"space": space_to_event_payload(space)},
            event_type="SpaceDeleted",
            event_version="1.2.0",
        )


class SpaceUserAddedEvent(Event):
    def __init__(self, user: User, space: Community):
        super().__init__(
            data={"user": user_to_event_payload(user), "space": space_to_event_payload(space)},
            event_type="SpaceUserAdded",
            event_version="1.2.0",
        )


class SpaceUpdatedEvent(Event):
    def __init__(self, creator: User, space: Community):
        super().__init__(
            data={"creator": user_to_event_payload(creator), "space": space_to_event_payload(space)},
            event_type="SpaceUpdated",
            event_version="1.2.0",
        )


class SpaceCreatedEvent(Event):
    def __init__(self, creator: User, space: Community):
        super().__init__(
            data={"creator": user_to_event_payload(creator), "space": space_to_event_payload(space)},
            event_type="SpaceCreated",
            event_version="1.2.0",
        )


def task_to_event_payload(task: Task) -> Dict[str, Any]:
    return {
        "id": str(task.id),
        "name": task.name,
        "description": task.description,
        "created": task.created.isoformat() if task.created else None,
        "timeframeStartDate": task.timeframe_start_date.isoformat() if task.timeframe_start_date else None,
        "timeframeEndDate": task.timeframe_end_date.isoformat() if task.timeframe_end_date else None,
        "regularity": task.regularity,
        "duration": task.duration,
        "slotsAvailable": task.slots_available,
        "slotsTaken": task.slots_taken,
        "visibility": task.visibility,
        "locationType": task.location_type,
        "location": task.location,
        "geolocationGeoJSON": task.geolocation_geojson,
        "skillsV2": task.skills_v2,
        "thumbnail": task.thumbnail.url if task.thumbnail else None,
        "contactEmail": task.contact_email,
        "contactPhone": task.contact_phone,
    }


class TaskCreatedEvent(Event):
    def __init__(self, user: User, task: Task):
        super().__init__(
            data={
                "user": user_to_event_payload(user),
                "space": space_to_event_payload(task.community),
                "task": task_to_event_payload(task),
            },
            event_type="TaskCreated",
            event_version="1.0.0",
        )


class TaskUpdatedEvent(Event):
    def __init__(self, user: User, task: Task):
        super().__init__(
            data={
                "user": user_to_event_payload(user),
                "space": space_to_event_payload(task.community),
                "task": task_to_event_payload(task),
            },
            event_type="TaskUpdated",
            event_version="1.0.0",
        )


class TaskDeletedEvent(Event):
    def __init__(self, user: User, task: Task):
        super().__init__(
            data={
                "user": user_to_event_payload(user),
                "space": space_to_event_payload(task.community),
                "task": task_to_event_payload(task),
            },
            event_type="TaskDeleted",
            event_version="1.0.0",
        )


def publish_space_created_event(community: Community):
    publish_event(event=SpaceCreatedEvent(community.creator, community), topic=PubSubTopic.OKUNA.value)


def publish_space_updated_event(community: Community):
    publish_event(event=SpaceUpdatedEvent(community.creator, community), topic=PubSubTopic.OKUNA.value)


def publish_space_user_added_event(username: str, community: Community):
    space_member: User = User.objects.get(username=username)
    publish_event(event=SpaceUserAddedEvent(space_member, community), topic=PubSubTopic.OKUNA.value)


def publish_space_deleted_event(community: Community):
    publish_event(event=SpaceDeletedEvent(community), topic=PubSubTopic.OKUNA.value)


def publish_space_user_left_event(user: User, community: Community):
    publish_event(event=SpaceUserLeftEvent(user, community), topic=PubSubTopic.OKUNA.value)


def publish_space_user_removed_event(user: User, community: Community):
    publish_event(event=SpaceUserRemovedEvent(user, community), topic=PubSubTopic.OKUNA.value)


def publish_task_created_event(user: User, task: Task) -> None:
    publish_event(event=TaskCreatedEvent(user, task), topic=PubSubTopic.OKUNA.value)


def publish_task_updated_event(user: User, task: Task) -> None:
    publish_event(event=TaskUpdatedEvent(user, task), topic=PubSubTopic.OKUNA.value)


def publish_task_deleted_event(user: User, task: Task) -> None:
    publish_event(event=TaskDeletedEvent(user, task), topic=PubSubTopic.OKUNA.value)
