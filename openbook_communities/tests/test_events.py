import json
from typing import Any

import pytest

from openbook_auth.events import UserPayload
from openbook_auth.models import User
from openbook_common.tests.helpers import make_community, make_user, make_community_task
from openbook_communities.events import (
    SpacePayload,
    SpaceUserRemovedEvent,
    SpaceUserLeftEvent,
    SpaceDeletedEvent,
    SpaceUserAddedEvent,
    SpaceCreatedEvent,
    SpaceUpdatedEvent,
    TaskCreatedEvent,
    TaskUpdatedEvent,
    TaskDeletedEvent,
)
from openbook_communities.models import Community, Task


# noinspection DuplicatedCode
def expected_user_payload(user: User) -> dict[str, Any]:
    return {
        "id": str(user.username),
        "name": user.profile.full_name(),
        "email": user.email,
        "identity": user.identity,
        "avatar": user.profile.avatar.url if user.profile.avatar else None,
        "aboutMe": user.profile.about_me,
        "location": user.profile.location,
    }


# noinspection DuplicatedCode
def expected_space_payload(community: Community) -> dict[str, Any]:
    return {
        "id": str(community.id),
        "name": community.title,
        "slug": community.name,
        "avatar": community.avatar.url if community.avatar else None,
        "description": community.description,
        "location": community.location,
        "locationLatLng": (
            {
                "latitude": community.geolocation.x,
                "longitude": community.geolocation.y,
            }
            if community.geolocation
            else None
        ),
    }


def expected_task_payload(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
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


@pytest.mark.django_db
def test_serialization_space_created_event():
    # GIVEN
    user = make_user()
    space = make_community(creator=user)

    # WHEN
    event = SpaceCreatedEvent(UserPayload.from_user(user), SpacePayload.from_community(space))

    # THEN
    expected_event_dict = {
        "eventType": "SpaceCreated",
        "eventVersion": "1.1.0",
        "data": (
            json.dumps({"creator": expected_user_payload(user), "space": expected_space_payload(space)}).encode(
                "utf-8"
            )
        ),
    }
    assert event.to_dict() == expected_event_dict


@pytest.mark.django_db
def test_serialization_space_updated_event():
    # GIVEN
    user = make_user()
    space = make_community(creator=user)

    # WHEN
    event = SpaceUpdatedEvent(UserPayload.from_user(user), SpacePayload.from_community(space))

    # THEN
    expected_event_dict = {
        "eventType": "SpaceUpdated",
        "eventVersion": "1.1.0",
        "data": (
            json.dumps({"creator": expected_user_payload(user), "space": expected_space_payload(space)}).encode(
                "utf-8"
            )
        ),
    }
    assert event.to_dict() == expected_event_dict


@pytest.mark.django_db
def test_serialization_space_deleted_event():
    # GIVEN
    space = make_community()

    # WHEN
    event = SpaceDeletedEvent(SpacePayload.from_community(space))

    # THEN
    expected_event_dict = {
        "eventType": "SpaceDeleted",
        "eventVersion": "1.1.0",
        "data": (json.dumps({"space": expected_space_payload(space)}).encode("utf-8")),
    }
    assert event.to_dict() == expected_event_dict


@pytest.mark.django_db
def test_serialization_space_user_added_event():
    # GIVEN
    user = make_user()
    space = make_community()

    # WHEN
    event = SpaceUserAddedEvent(UserPayload.from_user(user), SpacePayload.from_community(space))

    # THEN
    expected_event_dict = {
        "eventType": "SpaceUserAdded",
        "eventVersion": "1.1.0",
        "data": (
            json.dumps({"user": expected_user_payload(user), "space": expected_space_payload(space)}).encode("utf-8")
        ),
    }
    assert event.to_dict() == expected_event_dict


@pytest.mark.django_db
def test_serialization_space_user_left_event():
    # GIVEN
    user = make_user()
    space = make_community()

    # WHEN
    event = SpaceUserLeftEvent(UserPayload.from_user(user), SpacePayload.from_community(space))

    # THEN
    expected_event_dict = {
        "eventType": "SpaceUserLeft",
        "eventVersion": "1.1.0",
        "data": (
            json.dumps({"user": expected_user_payload(user), "space": expected_space_payload(space)}).encode("utf-8")
        ),
    }
    assert event.to_dict() == expected_event_dict


@pytest.mark.django_db
def test_serialization_space_user_removed_event():
    # GIVEN
    user = make_user()
    space = make_community()

    # WHEN
    event = SpaceUserRemovedEvent(UserPayload.from_user(user), SpacePayload.from_community(space))

    # THEN
    expected_event_dict = {
        "eventType": "SpaceUserRemoved",
        "eventVersion": "1.1.0",
        "data": (
            json.dumps({"user": expected_user_payload(user), "space": expected_space_payload(space)}).encode("utf-8")
        ),
    }
    assert event.to_dict() == expected_event_dict


@pytest.mark.django_db
def test_serialization_task_created_event():
    # GIVEN
    user = make_user()
    space = make_community()
    task = make_community_task(space)

    # WHEN
    event = TaskCreatedEvent(user, task)

    expected_event_dict = {
        "eventType": "TaskCreated",
        "eventVersion": "1.0.0",
        "data": (
            json.dumps(
                {
                    "user": expected_user_payload(user),
                    "space": expected_space_payload(space),
                    "task": expected_task_payload(task),
                }
            ).encode("utf-8")
        ),
    }
    assert event.to_dict() == expected_event_dict


@pytest.mark.django_db
def test_serialization_task_updated_event():
    # GIVEN
    user = make_user()
    space = make_community()
    task = make_community_task(space)

    # WHEN
    event = TaskUpdatedEvent(user, task)

    expected_event_dict = {
        "eventType": "TaskUpdated",
        "eventVersion": "1.0.0",
        "data": (
            json.dumps(
                {
                    "user": expected_user_payload(user),
                    "space": expected_space_payload(space),
                    "task": expected_task_payload(task),
                }
            ).encode("utf-8")
        ),
    }
    assert event.to_dict() == expected_event_dict


@pytest.mark.django_db
def test_serialization_task_deleted_event():
    # GIVEN
    user = make_user()
    space = make_community()
    task = make_community_task(space)

    # WHEN
    event = TaskDeletedEvent(user, task)

    expected_event_dict = {
        "eventType": "TaskDeleted",
        "eventVersion": "1.0.0",
        "data": (
            json.dumps(
                {
                    "user": expected_user_payload(user),
                    "space": expected_space_payload(space),
                    "task": expected_task_payload(task),
                }
            ).encode("utf-8")
        ),
    }
    assert event.to_dict() == expected_event_dict
