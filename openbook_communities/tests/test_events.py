import json
import pytest

from typing import Any

from openbook_auth.models import User
from openbook_common.tests.helpers import make_community, make_user
from openbook_communities.events.events import (
    SpaceCreatedEvent,
    SpaceDeletedEvent,
    SpaceUserAddedEvent,
    SpaceUserLeftEvent,
    SpaceUserRemovedEvent,
    UserDeletedEvent,
    UserNameUpdatedEvent,
)
from openbook_communities.events.payloads import SpacePayload, UserPayload
from openbook_communities.models import Community


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


@pytest.mark.django_db
def test_should_create_space_created_event():
    # GIVEN
    user = make_user()
    space = make_community(creator=user)

    # WHEN
    event = SpaceCreatedEvent(UserPayload.from_user(user), SpacePayload.from_community(space))
    event_dict = event.to_dict()

    # THEN
    data = {"creator": expected_user_payload(user), "space": expected_space_payload(space)}
    encoded_data = json.dumps(data).encode("utf-8")
    expected_event_dict = {"eventType": "SpaceCreated", "eventVersion": "1.1.0", "data": encoded_data}

    assert expected_event_dict == event_dict


@pytest.mark.django_db
def test_should_create_space_user_added_event():
    # GIVEN
    user = make_user()
    space = make_community()

    # WHEN
    event = SpaceUserAddedEvent(UserPayload.from_user(user), SpacePayload.from_community(space))
    event_dict = event.to_dict()

    # THEN
    data = {"user": expected_user_payload(user), "space": expected_space_payload(space)}
    encoded_data = json.dumps(data).encode("utf-8")
    expected_event_dict = {"eventType": "SpaceUserAdded", "eventVersion": "1.1.0", "data": encoded_data}

    assert expected_event_dict == event_dict


@pytest.mark.django_db
def test_should_create_user_name_updated_event():
    # GIVEN
    user = make_user()

    # WHEN
    event = UserNameUpdatedEvent(UserPayload.from_user(user))
    event_dict = event.to_dict()

    # THEN
    data = {"user": expected_user_payload(user)}
    encoded_data = json.dumps(data).encode("utf-8")
    expected_event_dict = {"eventType": "UserNameUpdated", "eventVersion": "1.1.0", "data": encoded_data}

    assert expected_event_dict == event_dict


@pytest.mark.django_db
def test_should_create_space_deleted_event():
    # GIVEN
    space = make_community()

    # WHEN
    event = SpaceDeletedEvent(SpacePayload.from_community(space))
    event_dict = event.to_dict()

    # THEN
    data = {"space": expected_space_payload(space)}
    encoded_data = json.dumps(data).encode("utf-8")
    expected_event_dict = {"eventType": "SpaceDeleted", "eventVersion": "1.1.0", "data": encoded_data}

    assert expected_event_dict == event_dict


@pytest.mark.django_db
def test_should_create_user_deleted_event():
    # GIVEN
    user = make_user()

    # WHEN
    event = UserDeletedEvent(UserPayload.from_user(user))
    event_dict = event.to_dict()

    # THEN
    data = {"user": expected_user_payload(user)}
    encoded_data = json.dumps(data).encode("utf-8")
    expected_event_dict = {"eventType": "UserDeleted", "eventVersion": "1.1.0", "data": encoded_data}

    assert expected_event_dict == event_dict


@pytest.mark.django_db
def test_should_create_space_user_left_event():
    # GIVEN
    user = make_user()
    space = make_community()

    # WHEN
    event = SpaceUserLeftEvent(UserPayload.from_user(user), SpacePayload.from_community(space))
    event_dict = event.to_dict()

    # THEN
    data = {"user": expected_user_payload(user), "space": expected_space_payload(space)}
    encoded_data = json.dumps(data).encode("utf-8")
    expected_event_dict = {"eventType": "SpaceUserLeft", "eventVersion": "1.1.0", "data": encoded_data}

    assert expected_event_dict == event_dict


@pytest.mark.django_db
def test_should_create_space_user_removed_event():
    # GIVEN
    user = make_user()
    space = make_community()

    # WHEN
    event = SpaceUserRemovedEvent(UserPayload.from_user(user), SpacePayload.from_community(space))
    event_dict = event.to_dict()

    # THEN
    data = {"user": expected_user_payload(user), "space": expected_space_payload(space)}
    encoded_data = json.dumps(data).encode("utf-8")
    expected_event_dict = {"eventType": "SpaceUserRemoved", "eventVersion": "1.1.0", "data": encoded_data}

    assert expected_event_dict == event_dict
