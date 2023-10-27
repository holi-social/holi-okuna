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
        space = make_community(title="Test Space")
        payload = SpaceMembershipRequestPayload(
            user=user,
            space=space,
            message="I'm interested in becoming a member of your space",
        )
        payload_dict = payload.to_dict()
        expected_result = {
            "userId": str(user.id),
            "userFullName": "Test User",
            "userEmail": "test.user@holi.social",
            "userAvatar": user.profile.avatar.url,
            "userAvatarBlurhash": "",
            "userAvatarDefaultColor": user.avatar_default_color,
            "spaceId": str(space.id),
            "spaceName": "test-space",
            "spaceTitle": "Test Space",
            "spaceCover": "",
            "spaceAvatar": "",
            "spaceAvatarBlurhash": "",
            "spaceAvatarDefaultColor": space.avatar_default_color,
            "requestMessage": "I'm interested in becoming a member of your space",
            "notificationType": "SPACE_MEMBERSHIP_REQUEST",
            "notificationVersion": "1.0.0",
        }
        self.assertDictContainsSubset(expected_result, flatten_payload(payload_dict))
