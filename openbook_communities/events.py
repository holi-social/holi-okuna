from enum import Enum
from typing import Optional, Dict, Any

import structlog
from django.contrib.gis.geos.point import Point

from openbook_auth.events import UserPayload
from openbook_auth.models import User
from openbook_common.pubsub.event import Event
from openbook_common.pubsub.publisher import publish_event
from openbook_common.pubsub.topic import Topic as PubSubTopic
from openbook_communities.models import Community, Task

logger = structlog.getLogger(__name__)


class SpacePayload:
    def __init__(
        self,
        id: str,
        name: str,
        slug: str,
        avatar: str,
        description: Optional[str] = None,
        location: Optional[str] = None,
        location_lat_lng: Optional[Point] = None,
    ):
        self.id = id
        self.name = name
        self.avatar = avatar
        self.slug = slug
        self.description = description
        self.location = location
        self.location_lat_lng = location_lat_lng
        # TODO add topics_v2

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "avatar": self.avatar,
            "description": self.description,
            "location": self.location,
            "locationLatLng": (
                {
                    "latitude": self.location_lat_lng.x,
                    "longitude": self.location_lat_lng.y,
                }
                if self.location_lat_lng
                else None
            ),
        }

    @classmethod
    def from_community(cls, community: Community):
        if community.avatar:
            avatarUrl = community.avatar.url
        else:
            avatarUrl = None

        return cls(
            id=str(community.id),
            name=community.title,
            slug=community.name,
            avatar=avatarUrl,
            description=community.description,
            location=community.location,
            location_lat_lng=community.geolocation,
        )


class SpaceUserRemovedEvent(Event):
    EVENT_VERSION = "1.1.0"

    def __init__(self, user: UserPayload, space: SpacePayload):
        super().__init__(
            data={"user": user.to_dict(), "space": space.to_dict()},
            event_type=SpaceEventType.SPACE_USER_REMOVED.value,
            event_version=SpaceUserRemovedEvent.EVENT_VERSION,
        )


class SpaceUserLeftEvent(Event):
    EVENT_VERSION = "1.1.0"

    def __init__(self, user: UserPayload, space: SpacePayload):
        super().__init__(
            data={"user": user.to_dict(), "space": space.to_dict()},
            event_type=SpaceEventType.SPACE_USER_LEFT.value,
            event_version=SpaceUserLeftEvent.EVENT_VERSION,
        )


class SpaceDeletedEvent(Event):
    EVENT_VERSION = "1.1.0"

    def __init__(self, space: SpacePayload):
        super().__init__(
            data={"space": space.to_dict()},
            event_type=SpaceEventType.SPACE_DELETED.value,
            event_version=SpaceDeletedEvent.EVENT_VERSION,
        )


class SpaceUserAddedEvent(Event):
    EVENT_VERSION = "1.1.0"

    def __init__(self, user: UserPayload, space: SpacePayload):
        super().__init__(
            data={"user": user.to_dict(), "space": space.to_dict()},
            event_type=SpaceEventType.SPACE_USER_ADDED.value,
            event_version=SpaceUserAddedEvent.EVENT_VERSION,
        )


class SpaceUpdatedEvent(Event):
    EVENT_VERSION = "1.1.0"

    def __init__(self, creator: UserPayload, space: SpacePayload):
        super().__init__(
            data={"creator": creator.to_dict(), "space": space.to_dict()},
            event_type=SpaceEventType.SPACE_UPDATED.value,
            event_version=SpaceUpdatedEvent.EVENT_VERSION,
        )


class SpaceCreatedEvent(Event):
    EVENT_VERSION = "1.1.0"

    def __init__(self, creator: UserPayload, space: SpacePayload):
        super().__init__(
            data={"creator": creator.to_dict(), "space": space.to_dict()},
            event_type=SpaceEventType.SPACE_CREATED.value,
            event_version=SpaceCreatedEvent.EVENT_VERSION,
        )


class SpaceEventType(Enum):
    SPACE_CREATED = "SpaceCreated"
    SPACE_UPDATED = "SpaceUpdated"
    SPACE_DELETED = "SpaceDeleted"

    SPACE_USER_ADDED = "SpaceUserAdded"
    SPACE_USER_LEFT = "SpaceUserLeft"
    SPACE_USER_REMOVED = "SpaceUserRemoved"


def _task_to_dict(task: Task) -> Dict[str, Any]:
    return {
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
                "user": UserPayload.from_user(user).to_dict(),
                "space": SpacePayload.from_community(task.community).to_dict(),
                "task": _task_to_dict(task),
            },
            event_type="TaskCreated",
            event_version="1.0.0",
        )


class TaskUpdatedEvent(Event):
    def __init__(self, user: User, task: Task):
        super().__init__(
            data={
                "user": UserPayload.from_user(user).to_dict(),
                "space": SpacePayload.from_community(task.community).to_dict(),
                "task": _task_to_dict(task),
            },
            event_type="TaskUpdated",
            event_version="1.0.0",
        )


class TaskDeletedEvent(Event):
    def __init__(self, user: User, task: Task):
        super().__init__(
            data={
                "user": UserPayload.from_user(user).to_dict(),
                "space": SpacePayload.from_community(task.community).to_dict(),
                "task": _task_to_dict(task),
            },
            event_type="TaskDeleted",
            event_version="1.0.0",
        )


def publish_space_created_event(community: Community):
    creator = UserPayload.from_user(community.creator)
    space = SpacePayload.from_community(community)
    event = SpaceCreatedEvent(creator, space)
    publish_event(event=event, topic=PubSubTopic.OKUNA.value)


def publish_space_updated_event(community: Community):
    creator = UserPayload.from_user(community.creator)
    space = SpacePayload.from_community(community)
    event = SpaceUpdatedEvent(creator, space)
    publish_event(event=event, topic=PubSubTopic.OKUNA.value)


def publish_space_user_added_event(username: str, community: Community):
    space_member: User = User.objects.get(username=username)
    user = UserPayload.from_user(space_member)
    space = SpacePayload.from_community(community)
    event = SpaceUserAddedEvent(user, space)
    publish_event(event=event, topic=PubSubTopic.OKUNA.value)


def publish_space_deleted_event(community: Community):
    space = SpacePayload.from_community(community)
    event = SpaceDeletedEvent(space)
    publish_event(event=event, topic=PubSubTopic.OKUNA.value)


def publish_space_user_left_event(user: User, community: Community):
    user = UserPayload.from_user(user)
    space = SpacePayload.from_community(community)
    event = SpaceUserLeftEvent(user, space)
    publish_event(event=event, topic=PubSubTopic.OKUNA.value)


def publish_space_user_removed_event(user: User, community: Community):
    user = UserPayload.from_user(user)
    space = SpacePayload.from_community(community)
    event = SpaceUserRemovedEvent(user, space)
    publish_event(event=event, topic=PubSubTopic.OKUNA.value)


def publish_task_created_event(user: User, task: Task) -> None:
    publish_event(event=TaskCreatedEvent(user, task), topic=PubSubTopic.OKUNA.value)


def publish_task_updated_event(user: User, task: Task) -> None:
    publish_event(event=TaskUpdatedEvent(user, task), topic=PubSubTopic.OKUNA.value)


def publish_task_deleted_event(user: User, task: Task) -> None:
    publish_event(event=TaskDeletedEvent(user, task), topic=PubSubTopic.OKUNA.value)
