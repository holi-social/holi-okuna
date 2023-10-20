from unittest import TestCase

import pytest
from openbook_common.tests.helpers import make_user, make_community

from openbook_notifications.helpers import flatten_payload
from openbook_notifications.payloads import SpaceMembershipRequestPayload


@pytest.mark.django_db
class TestFlattenPayload(TestCase):
    def test_flatten_payload_simple(self):
        data_dict = {"key1": "value1", "key2": "value2"}
        expected_result = {"key1": "value1", "key2": "value2"}
        self.assertEqual(flatten_payload(data_dict), expected_result)

    def test_flatten_payload_complex(self):
        user = make_user(name="Test", last_name="User", email="test.user@holi.social")
        space = make_community(title="Test Community")
        payload = SpaceMembershipRequestPayload(
            user=user,
            space=space,
            message="I'm interested in becoming a member of your space",
        )
        payload_dict = payload.to_dict()
        data_dict = payload_dict["data"]
        expected_result = {
            "user_id": str(user.id),
            "user_full_name": "Test User",
            "user_email": "test.user@holi.social",
            "user_avatar": user.profile.avatar.url,
            "space_id": str(space.id),
            "space_name": "Test Community",
            "space_cover": "",
            "space_avatar": "",
            "request_message": "I'm interested in becoming a member of your space",
        }
        self.assertDictContainsSubset(expected_result, flatten_payload(data_dict))
