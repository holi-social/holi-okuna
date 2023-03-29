import json

from django.test import testcases
from openbook_communities.events.events import SpaceCreatedEvent, SpaceUserAddedEvent

from openbook_communities.events.payloads import SpacePayload, UserPayload
from openbook_common.tests.helpers import make_community, make_user


class SpaceCreatedEventTestCase(testcases.TestCase):
    def test_should_create_space_created_event(self):
        user = make_user()
        community = make_community(creator=user)

        creator = UserPayload.from_user(user)
        space = SpacePayload.from_community(community)

        data = {"creator": creator.to_dict(), "space": space.to_dict()}

        encoded_data = json.dumps(data).encode("utf-8")

        event = SpaceCreatedEvent(creator, space)

        event_dict = event.to_dict()

        eventPayload = {"eventType": "SpaceCreated", "eventVersion": "1.0.0", "data": encoded_data}

        self.assertEqual(eventPayload, event_dict)


class SpaceUserAddedEventTestCase(testcases.TestCase):
    def test_should_create_space_user_added_event(self):
        user = make_user()
        community = make_community()

        user = UserPayload.from_user(user)
        space = SpacePayload.from_community(community)

        data = {"user": user.to_dict(), "space": space.to_dict()}

        encoded_data = json.dumps(data).encode("utf-8")

        event = SpaceUserAddedEvent(user, space)

        event_dict = event.to_dict()

        eventPayload = {"eventType": "SpaceUserAdded", "eventVersion": "1.0.0", "data": encoded_data}

        self.assertEqual(eventPayload, event_dict)
