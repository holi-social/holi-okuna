import json

from django.test import testcases

from openbook_common.pubsub.events import SpaceCreatedEvent
from openbook_common.pubsub.payloads import Space, User
from openbook_common.tests.helpers import make_community, make_user


class SpaceCreatedEventTestCase(testcases.TestCase):
    def test_should_create_space_created_event(self):
        creator = make_user()
        community = make_community(creator=creator)

        user = User(id=str(creator.uuid), name=creator.profile.name, email=creator.email)
        space = Space(id=str(community.id), name=community.title, slug=community.name)

        data = {"user": user.to_dict(), "space": space.to_dict()}

        encoded_data = json.dumps(data).encode("utf-8")

        event = SpaceCreatedEvent(user, space)

        event_dict = event.to_dict()

        eventPayload = {"eventType": "SpaceCreated", "eventVersion": "1.0.0", "data": encoded_data}

        self.assertEqual(eventPayload, event_dict)
