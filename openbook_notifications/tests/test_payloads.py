import pytest

from django.test import TestCase
from openbook_common.tests.helpers import (
    make_community,
    make_user,
)

from openbook_notifications.payloads import (
    UserData,
    SpaceData,
    Payload,
    SpaceMembershipRequestPayload,
)


@pytest.mark.django_db
class TestPayloads(TestCase):
    def setUp(self):
        self.user = make_user(name="Test", last_name="User", email="test.user@holi.social")
        self.space = make_community(title="Test Space")
        self.notification_type = "TEST_NOTIFICATION_TYPE"

    def test_user_data_to_dict(self):
        user_data = UserData(
            id="test-user-id",
            full_name="Test User",
            email="test.user@holi.social",
            avatar="avatar.jpg",
        )
        data_dict = user_data.to_dict()

        self.assertEqual(
            data_dict,
            {
                "id": "test-user-id",
                "full_name": "Test User",
                "email": "test.user@holi.social",
                "avatar": "avatar.jpg",
            },
        )

    def test_user_data_from_user(self):
        user_data = UserData.from_user(self.user)
        data_dict = user_data.to_dict()

        self.assertEqual(
            data_dict,
            {
                "id": str(self.user.username),
                "full_name": "Test User",
                "email": "test.user@holi.social",
                "avatar": self.user.profile.avatar.url,
            },
        )

    def test_space_data_to_dict(self):
        space_data = SpaceData(
            id="test-space-id",
            name="test-space",
            title="Test Space",
            cover="cover.jpg",
            avatar="avatar.jpg",
        )
        data_dict = space_data.to_dict()

        self.assertEqual(
            data_dict,
            {
                "id": "test-space-id",
                "name": "test-space",
                "title": "Test Space",
                "cover": "cover.jpg",
                "avatar": "avatar.jpg",
            },
        )

    def test_space_data_from_community(self):
        space_data = SpaceData.from_community(self.space)
        data_dict = space_data.to_dict()

        self.assertEqual(
            data_dict,
            {"id": str(self.space.id), "name": "test-space", "title": "Test Space", "cover": "", "avatar": ""},
        )

    def test_payload_to_dict(self):
        data = {
            "key": "value",
        }
        payload = Payload(data=data, notification_type=self.notification_type, notification_version="1.0.0")
        data_dict = payload.to_dict()

        self.assertEqual(
            data_dict,
            {
                "data": data,
                "notification_type": self.notification_type,
                "notification_version": "1.0.0",
            },
        )

    def test_space_membership_request_payload(self):
        payload = SpaceMembershipRequestPayload(
            user=self.user,
            space=self.space,
            message="I'm interested in becoming a member of your space",
        )

        data_dict = payload.to_dict()

        self.assertEqual(data_dict["notification_type"], "SPACE_MEMBERSHIP_REQUEST")
        self.assertEqual(data_dict["notification_version"], "1.0.0")
        self.assertEqual(data_dict["data"]["user"]["id"], str(self.user.username))
        self.assertEqual(data_dict["data"]["space"]["id"], str(self.space.id))
        self.assertEqual(data_dict["data"]["request_message"], "I'm interested in becoming a member of your space")
        self.assertIsNotNone(data_dict["data"]["request_datetime"])
        self.assertEqual(
            data_dict["data"]["collaborators_link"],
            "https://staging.dev.holi.social/spaces/test-space/collaborators/manage?tab=pending&userId="
            + str(self.user.username),
        )
