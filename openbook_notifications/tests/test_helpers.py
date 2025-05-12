from unittest import TestCase

import pytest
from openbook_common.tests.helpers import make_user, make_community

from openbook_notifications.helpers import flatten_payload, replace_mentions_with_full_names
from openbook_notifications.payloads import SpaceMembershipRequestPayload


@pytest.mark.django_db
class TestFlattenPayload(TestCase):
    def test_flatten_payload_simple(self):
        data_dict = {"key1": "value1", "key2": "value2"}
        expected_result = {"key1": "value1", "key2": "value2"}
        self.assertEqual(flatten_payload(data_dict), expected_result)

    def test_flatten_payload_complex(self):
        # GIVEN
        user = make_user(name="Test", last_name="User", email="test.user@holi.social")
        space = make_community(title="Test Space")
        payload = SpaceMembershipRequestPayload(
            user=user,
            space=space,
            message="I'm interested in becoming a member of your space",
        )

        # WHEN
        flattened = flatten_payload(payload.to_dict())

        # THEN
        expected_result = {
            "userId": str(user.id),
            "userFullName": "Test User",
            "userAvatar": user.profile.avatar.url,
            "userAvatarBlurhash": "",
            "userAvatarDefaultColor": user.avatar_default_color,
            "spaceId": str(space.id),
            "spaceName": "test-space",
            "spaceTitle": "Test Space",
            "spaceAvatar": "",
            "spaceAvatarBlurhash": "",
            "spaceAvatarDefaultColor": space.avatar_default_color,
            "requestMessage": "I'm interested in becoming a member of your space",
            "notificationType": "SPACE_MEMBERSHIP_REQUEST",
            "notificationVersion": "1.0.0",
        }
        assert all(item in flattened for item in expected_result)


@pytest.mark.django_db
class TestReplaceMentions(TestCase):
    def test_replace_mentions_with_full_names_single_mention(self):
        mentioned_user = make_user()
        mentioned_users = [mentioned_user]

        text = f"@{mentioned_user.username} what do you think about this post?"
        expected_result = f"{mentioned_user.profile.full_name()} what do you think about this post?"

        self.assertEqual(replace_mentions_with_full_names(text, mentioned_users), expected_result)

    def test_replace_mentions_with_full_names_multiple_mentions(self):
        mentioned_user = make_user()
        another_mentioned_user = make_user()
        mentioned_users = [mentioned_user, another_mentioned_user]

        text = f"What do you think, @{mentioned_user.username} and @{another_mentioned_user.username}?"
        expected_result = f"What do you think, {mentioned_user.profile.full_name()} and {another_mentioned_user.profile.full_name()}?"

        self.assertEqual(replace_mentions_with_full_names(text, mentioned_users), expected_result)
