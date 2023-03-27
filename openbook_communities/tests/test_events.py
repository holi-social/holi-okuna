import json

from django.test import testcases
from openbook_communities.events.events import SpaceCreatedEvent

from openbook_communities.events.payloads import SpacePayload, UserPayload
from openbook_common.tests.helpers import make_community, make_user


class SpaceCreatedEventTestCase(testcases.TestCase):
    def test_should_create_space_created_event(self):
        creator = make_user()
        community = make_community(creator=creator)

        creator = UserPayload(id=str(creator.username), name=creator.profile.name, email=creator.email)
        space = SpacePayload(id=str(community.id), name=community.title, slug=community.name)

        data = {"creator": creator.to_dict(), "space": space.to_dict()}

        encoded_data = json.dumps(data).encode("utf-8")

        event = SpaceCreatedEvent(creator, space)

        event_dict = event.to_dict()

        eventPayload = {"eventType": "SpaceCreated", "eventVersion": "1.0.0", "data": encoded_data}

        self.assertEqual(eventPayload, event_dict)
