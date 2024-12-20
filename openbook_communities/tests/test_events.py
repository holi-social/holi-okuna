import json

from typing import Any
from django.test import testcases

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


def expected_user_payload(user: User) -> dict[str, Any]:
    return {
        "id": str(user.username),
        "name": user.profile.full_name(),
        "email": user.email,
        "identity": user.identity,
        "avatar": user.profile.avatar.url if user.profile.avatar else None,
        "aboutMe": user.profile.about_me,
        "location": user.profile.geolocation.name if user.profile.geolocation else None,
    }


# noinspection DuplicatedCode
def expected_space_payload(community: Community) -> dict[str, Any]:
    return {
        "id": str(community.id),
        "name": community.title,
        "slug": community.name,
        "avatar": community.avatar.url if community.avatar else None,
        "avatarDefaultColor": community.avatar_default_color,
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


class SpaceCreatedEventTestCase(testcases.TestCase):
    def test_should_create_space_created_event(self):
        creator = make_user()
        community = make_community(creator=creator)

        creator_payload = UserPayload.from_user(creator)
        space_payload = SpacePayload.from_community(community)

        data = {"creator": expected_user_payload(creator), "space": expected_space_payload(community)}

        encoded_data = json.dumps(data).encode("utf-8")

        event = SpaceCreatedEvent(creator_payload, space_payload)

        event_dict = event.to_dict()

        eventPayload = {"eventType": "SpaceCreated", "eventVersion": "1.1.0", "data": encoded_data}

        self.assertEqual(eventPayload, event_dict)


class SpaceUserAddedEventTestCase(testcases.TestCase):
    def test_should_create_space_user_added_event(self):
        user = make_user()
        community = make_community()

        user_payload = UserPayload.from_user(user)
        space_payload = SpacePayload.from_community(community)

        data = {"user": expected_user_payload(user), "space": expected_space_payload(community)}

        encoded_data = json.dumps(data).encode("utf-8")

        event = SpaceUserAddedEvent(user_payload, space_payload)

        event_dict = event.to_dict()

        eventPayload = {"eventType": "SpaceUserAdded", "eventVersion": "1.1.0", "data": encoded_data}

        self.assertEqual(eventPayload, event_dict)


class UserNameUpdatedEventTestCase(testcases.TestCase):
    def test_should_create_user_name_updated_event(self):
        user = make_user()

        user_payload = UserPayload.from_user(user)

        data = {"user": expected_user_payload(user)}

        encoded_data = json.dumps(data).encode("utf-8")

        event = UserNameUpdatedEvent(user_payload)

        event_dict = event.to_dict()

        eventPayload = {"eventType": "UserNameUpdated", "eventVersion": "1.1.0", "data": encoded_data}

        self.assertEqual(eventPayload, event_dict)


class SpaceDeletedEventTestCase(testcases.TestCase):
    def test_should_create_space_deleted_event(self):
        community = make_community()

        space_payload = SpacePayload.from_community(community)

        data = {"space": expected_space_payload(community)}

        encoded_data = json.dumps(data).encode("utf-8")

        event = SpaceDeletedEvent(space_payload)

        event_dict = event.to_dict()

        eventPayload = {"eventType": "SpaceDeleted", "eventVersion": "1.1.0", "data": encoded_data}

        self.assertEqual(eventPayload, event_dict)


class UserDeletedEventTestCase(testcases.TestCase):
    def test_should_create_space_deleted_event(self):
        user = make_user()

        user_payload = UserPayload.from_user(user)

        data = {"user": expected_user_payload(user)}

        encoded_data = json.dumps(data).encode("utf-8")

        event = UserDeletedEvent(user_payload)

        event_dict = event.to_dict()

        eventPayload = {"eventType": "UserDeleted", "eventVersion": "1.1.0", "data": encoded_data}

        self.assertEqual(eventPayload, event_dict)


class SpaceUserLeftEventTestCase(testcases.TestCase):
    def test_should_create_space_user_left_event(self):
        user = make_user()
        community = make_community()

        user_payload = UserPayload.from_user(user)
        space_payload = SpacePayload.from_community(community)

        data = {"user": expected_user_payload(user), "space": expected_space_payload(community)}

        encoded_data = json.dumps(data).encode("utf-8")

        event = SpaceUserLeftEvent(user_payload, space_payload)

        event_dict = event.to_dict()

        eventPayload = {"eventType": "SpaceUserLeft", "eventVersion": "1.1.0", "data": encoded_data}

        self.assertEqual(eventPayload, event_dict)


class SpaceUserRemovedEventTestCase(testcases.TestCase):
    def test_should_create_space_user_removed_event(self):
        user = make_user()
        community = make_community()

        user_payload = UserPayload.from_user(user)
        space_payload = SpacePayload.from_community(community)

        data = {"user": expected_user_payload(user), "space": expected_space_payload(community)}

        encoded_data = json.dumps(data).encode("utf-8")

        event = SpaceUserRemovedEvent(user_payload, space_payload)

        event_dict = event.to_dict()

        eventPayload = {"eventType": "SpaceUserRemoved", "eventVersion": "1.1.0", "data": encoded_data}

        self.assertEqual(eventPayload, event_dict)
