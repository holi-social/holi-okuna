from unittest import mock

import pytest
from django.test import TestCase
from novu.api import EventApi

from openbook import settings
from openbook_common.tests.helpers import (
    make_community,
    make_community_post,
    make_space_post_comment,
    make_user,
    make_space_post_comment_with_mention,
    make_feed_post_comment_with_mention,
    make_insight_discussion_comment_with_mention,
    make_insight,
)
from openbook_notifications.helpers import replace_mentions_with_full_names
from openbook_notifications.payloads import (
    NotificationType,
    Payload,
    PostCommentAuthorPayload,
    PostCommentMentionPayload,
    SpaceData,
    SpaceMembershipInviteApprovalPayload,
    SpaceMembershipInviteDeclinePayload,
    SpaceMembershipInvitePayload,
    SpaceMembershipRequestApprovalAdminPayload,
    SpaceMembershipRequestApprovalUserPayload,
    SpaceMembershipRequestDeclinePayload,
    SpaceMembershipRequestPayload,
    SpaceNewPostPayload,
    UserData,
)


@pytest.fixture(scope="class")
def mock_novu_api():
    with mock.patch.object(EventApi, "trigger"):
        # prevent sending novu notifications
        yield


@pytest.mark.usefixtures("mock_novu_api")
@pytest.mark.django_db
class TestPayloads(TestCase):
    def setUp(self):
        self.user = make_user(name="Test", last_name="User")
        self.admin = make_user(name="Test", last_name="Admin")
        self.space = make_community(title="Test Space", creator=self.admin)
        self.notification_type = "TEST_NOTIFICATION_TYPE"
        self.approver = make_user(name="Test", last_name="Approver")
        self.post = make_community_post()
        self.space_post_comment = make_space_post_comment()
        self.space_post_comment_with_mention = make_space_post_comment_with_mention()
        self.feed_post_comment_with_mention = make_feed_post_comment_with_mention()
        self.insight = make_insight()
        self.insight_discussion_comment_with_mention = make_insight_discussion_comment_with_mention()

    def test_user_data_to_dict(self):
        user_data = UserData(
            id="test-user-id",
            full_name="Test User",
            avatar="avatar.jpg",
            avatar_blurhash="test_blurhash",
            avatar_default_color="#FFF000",
            avatar_label="TU",
            profile_link=f"{settings.APP_URL}/profile/test-user-id",
        )
        result = user_data.to_dict()

        self.assertEqual(
            result,
            {
                "id": "test-user-id",
                "fullName": "Test User",
                "avatar": "avatar.jpg",
                "avatarBlurhash": "test_blurhash",
                "avatarDefaultColor": "#FFF000",
                "avatarLabel": "TU",
                "profileLink": f"{settings.APP_URL}/profile/test-user-id",
            },
        )

    def test_user_data_from_user(self):
        user_data = UserData.from_user(self.user)
        result = user_data.to_dict()

        self.assertEqual(
            result,
            {
                "id": str(self.user.username),
                "fullName": "Test User",
                "avatar": self.user.profile.avatar.url,
                "avatarBlurhash": "",
                "avatarDefaultColor": self.user.avatar_default_color,
                "avatarLabel": self.user.avatar_label,
                "profileLink": f"{settings.APP_URL}/profile/{self.user.username}",
            },
        )

    def test_space_data_to_dict(self):
        space_data = SpaceData(
            id=self.space.id,
            name="test-space",
            title="Test Space",
            avatar="avatar.jpg",
            avatar_blurhash="test-blurhash",
            avatar_default_color="#FFF000",
            goal="test-goal",
            link=f"{settings.APP_URL}/spaces/{self.space.id}",
            cover="cover.jpg",
        )
        result = space_data.to_dict()

        self.assertEqual(
            result,
            {
                "id": self.space.id,
                "name": "test-space",
                "title": "Test Space",
                "avatar": "avatar.jpg",
                "avatarBlurhash": "test-blurhash",
                "avatarDefaultColor": "#FFF000",
                "goal": "test-goal",
                "link": f"{settings.APP_URL}/spaces/{self.space.id}",
                "cover": "cover.jpg",
            },
        )

    def test_space_data_from_community(self):
        space_data = SpaceData.from_community(self.space)
        result = space_data.to_dict()

        self.assertEqual(
            result,
            {
                "id": str(self.space.id),
                "name": "test-space",
                "title": "Test Space",
                "avatar": "",
                "avatarBlurhash": "",
                "avatarDefaultColor": self.space.avatar_default_color,
                "goal": self.space.description,
                "link": f"{settings.APP_URL}/spaces/{self.space.name}",
                "cover": self.space.cover.url if self.space.cover else "",
            },
        )

    def test_payload_to_dict(self):
        data = {
            "key": "value",
        }
        payload = Payload(data=data, notification_type=self.notification_type, notification_version="1.0.0")
        result = payload.to_dict()

        self.assertEqual(
            result,
            {
                "data": data,
                "notificationType": self.notification_type,
                "notificationVersion": "1.0.0",
            },
        )

    def test_space_membership_request_payload(self):
        payload = SpaceMembershipRequestPayload(
            user=self.user,
            space=self.space,
            message="I'm interested in becoming a member of your space",
        )

        result = payload.to_dict()

        self.assertEqual(result["notificationType"], "SPACE_MEMBERSHIP_REQUEST")
        self.assertEqual(result["notificationVersion"], "1.0.0")
        self.assertEqual(result["data"]["user"]["id"], str(self.user.username))
        self.assertEqual(result["data"]["space"]["id"], str(self.space.id))
        self.assertEqual(result["data"]["requestMessage"], "I'm interested in becoming a member of your space")
        self.assertIsNotNone(result["data"]["requestDatetime"])
        self.assertEqual(
            result["data"]["collaboratorsLink"],
            "https://staging.dev.holi.social/spaces/test-space/collaborators/manage?tab=pending&userId="
            + str(self.user.username),
        )

    def test_space_membership_request_approval_user_payload(self):
        payload = SpaceMembershipRequestApprovalUserPayload(user=self.user, space=self.space, approver=self.approver)

        result = payload.to_dict()

        self.assertEqual(result["notificationType"], "SPACE_MEMBERSHIP_REQUEST_APPROVAL_USER")
        self.assertEqual(result["notificationVersion"], "1.0.0")
        self.assertEqual(result["data"]["user"]["id"], str(self.user.username))
        self.assertEqual(result["data"]["space"]["id"], str(self.space.id))
        self.assertEqual(result["data"]["approver"]["id"], str(self.approver.id))
        self.assertIsNotNone(result["data"]["approvalDatetime"])

    def test_space_membership_request_approval_admin_payload(self):
        payload = SpaceMembershipRequestApprovalAdminPayload(
            user=self.user,
            space=self.space,
        )

        result = payload.to_dict()

        self.assertEqual(result["notificationType"], "SPACE_MEMBERSHIP_REQUEST_APPROVAL_ADMIN")
        self.assertEqual(result["notificationVersion"], "1.0.0")
        self.assertEqual(result["data"]["user"]["id"], str(self.user.username))
        self.assertEqual(result["data"]["space"]["id"], str(self.space.id))

        payload = SpaceMembershipRequestApprovalUserPayload(
            user=self.user,
            space=self.space,
            approver=self.admin,
        )

        result = payload.to_dict()

        self.assertEqual(result["notificationType"], "SPACE_MEMBERSHIP_REQUEST_APPROVAL_USER")
        self.assertEqual(result["notificationVersion"], "1.0.0")
        self.assertEqual(result["data"]["user"]["id"], str(self.user.username))
        self.assertEqual(result["data"]["space"]["id"], str(self.space.id))
        self.assertEqual(result["data"]["approver"]["id"], str(self.admin.username))
        self.assertIsNotNone(result["data"]["approvalDatetime"])
        self.assertEqual(
            result["data"]["spaceLink"],
            "https://staging.dev.holi.social/spaces/test-space",
        )

    def test_space_membership_request_decline_payload(self):
        payload = SpaceMembershipRequestDeclinePayload(
            user=self.user,
            space=self.space,
            denier=self.admin,
            notification_type=NotificationType.SPACE_MEMBERSHIP_REQUEST_DECLINE_USER.value,
        )

        result = payload.to_dict()

        self.assertEqual(result["notificationType"], "SPACE_MEMBERSHIP_REQUEST_DECLINE_USER")
        self.assertEqual(result["notificationVersion"], "1.0.0")
        self.assertEqual(result["data"]["user"]["id"], str(self.user.username))
        self.assertEqual(result["data"]["space"]["id"], str(self.space.id))
        self.assertEqual(result["data"]["denier"]["id"], str(self.admin.username))
        self.assertIsNotNone(result["data"]["denialDatetime"])

    def test_space_membership_invite_payload(self):
        payload = SpaceMembershipInvitePayload(
            user=self.user,
            space=self.space,
        )

        result = payload.to_dict()

        self.assertEqual(result["notificationType"], "SPACE_MEMBERSHIP_INVITE")
        self.assertEqual(result["notificationVersion"], "1.0.0")
        self.assertEqual(result["data"]["user"]["id"], str(self.user.username))
        self.assertEqual(result["data"]["space"]["id"], str(self.space.id))
        self.assertIsNotNone(result["data"]["inviteDatetime"])

    def test_space_membership_invite_approval_payload(self):
        payload = SpaceMembershipInviteApprovalPayload(
            user=self.user,
            space=self.space,
            notification_type=NotificationType.SPACE_MEMBERSHIP_INVITE_APPROVAL_USER.value,
        )

        result = payload.to_dict()

        self.assertEqual(result["notificationType"], "SPACE_MEMBERSHIP_INVITE_APPROVAL_USER")
        self.assertEqual(result["notificationVersion"], "1.0.0")
        self.assertEqual(result["data"]["user"]["id"], str(self.user.username))
        self.assertEqual(result["data"]["space"]["id"], str(self.space.id))

    def test_space_membership_invite_decline_payload(self):
        payload = SpaceMembershipInviteDeclinePayload(
            user=self.user,
            space=self.space,
            notification_type=NotificationType.SPACE_MEMBERSHIP_INVITE_DECLINE_USER.value,
        )

        result = payload.to_dict()

        self.assertEqual(result["notificationType"], "SPACE_MEMBERSHIP_INVITE_DECLINE_USER")
        self.assertEqual(result["notificationVersion"], "1.0.0")
        self.assertEqual(result["data"]["user"]["id"], str(self.user.username))
        self.assertEqual(result["data"]["space"]["id"], str(self.space.id))

    def test_can_map_space_post_comment_mention_payload(self):
        payload = PostCommentMentionPayload(
            comment=self.space_post_comment_with_mention,
            comment_commentable_context_id=self.space.id,
            notification_type=NotificationType.POST_COMMENT_MENTION.value,
        )

        result = payload.to_dict()

        self.assertIsNotNone(result["notificationVersion"])
        self.assertEqual(result["notificationType"], "POST_COMMENT_MENTION")
        self.assertEqual(result["data"]["user"]["id"], str(self.space_post_comment_with_mention.commenter.username))
        self.assertEqual(result["data"]["comment"]["id"], str(self.space_post_comment_with_mention.id))
        self.assertEqual(
            result["data"]["comment"]["text"],
            replace_mentions_with_full_names(
                text=self.space_post_comment_with_mention.text,
                mentioned_users=self.space_post_comment_with_mention.mentions.all(),
            ),
        )

        self.assertEqual(result["data"]["post"]["id"], str(self.space_post_comment_with_mention.commentable_id))
        self.assertEqual(result["data"]["post"]["title"], self.space_post_comment_with_mention.commentable.title)
        self.assertEqual(
            result["data"]["post"]["context"], self.space_post_comment_with_mention.commentable.community.title
        )

    def test_can_generate_space_post_comment_mention_notification_link(self):
        payload = PostCommentMentionPayload(
            comment=self.space_post_comment_with_mention,
            comment_commentable_context_id=self.space.id,
            notification_type=NotificationType.POST_COMMENT_MENTION.value,
        )

        result = payload.to_dict()

        self.assertEqual(
            result["data"]["commentLink"],
            f"/spaces/{self.space.id}/updates/{self.space_post_comment_with_mention.commentable_id}?commentId={self.space_post_comment_with_mention.id}",
        )

    def test_can_generate_feed_post_comment_mention_notification_link(self):
        payload = PostCommentMentionPayload(
            comment=self.feed_post_comment_with_mention,
            comment_commentable_context_id=self.space.id,
            notification_type=NotificationType.POST_COMMENT_MENTION.value,
        )

        result = payload.to_dict()
        self.assertEqual(
            result["data"]["commentLink"],
            f"/feed-posts/{self.feed_post_comment_with_mention.commentable_id}?commentId={self.feed_post_comment_with_mention.id}",
        )

    def test_can_generate_insight_discussion_comment_mention_notification_link(self):
        payload = PostCommentMentionPayload(
            comment=self.insight_discussion_comment_with_mention,
            comment_commentable_context_id=self.insight.id,
            notification_type=NotificationType.POST_COMMENT_MENTION.value,
        )

        result = payload.to_dict()
        self.assertEqual(
            result["data"]["commentLink"],
            f"/insights/{self.insight.id}/discussions/{self.insight_discussion_comment_with_mention.commentable_id}?commentId={self.insight_discussion_comment_with_mention.id}",
        )

    def test_post_comment_author_payload(self):
        payload = PostCommentAuthorPayload(
            comment=self.space_post_comment,
            comment_commentable_context_id=self.space.id,
            notification_type=NotificationType.POST_COMMENT_AUTHOR.value,
        )

        result = payload.to_dict()
        self.assertIsNotNone(result["notificationVersion"])
        self.assertEqual(result["notificationType"], "POST_COMMENT_AUTHOR")
        self.assertEqual(result["data"]["user"]["id"], str(self.space_post_comment.commentable.creator.username))
        self.assertEqual(result["data"]["commenter"]["id"], str(self.space_post_comment.commenter.username))
        self.assertEqual(result["data"]["comment"]["id"], str(self.space_post_comment.id))
        self.assertEqual(
            result["data"]["comment"]["text"],
            replace_mentions_with_full_names(
                text=self.space_post_comment.text, mentioned_users=self.space_post_comment.mentions.all()
            ),
        )
        self.assertEqual(result["data"]["post"]["id"], str(self.space_post_comment.commentable_id))
        self.assertEqual(result["data"]["post"]["title"], self.space_post_comment.commentable.title)
        self.assertIsNotNone(result["data"]["commentDatetime"])

    def test_space_new_post_payload(self):
        payload = SpaceNewPostPayload(
            post=self.post,
            notification_type=NotificationType.SPACE_NEW_POST.value,
        )

        result = payload.to_dict()
        self.assertEqual(result["notificationType"], "SPACE_NEW_POST")
        self.assertEqual(result["notificationVersion"], "1.0.0")
        self.assertEqual(result["data"]["user"]["id"], str(self.post.creator.username))
        self.assertEqual(result["data"]["post"]["id"], str(self.post.id))
        self.assertEqual(result["data"]["space"]["id"], str(self.post.community.id))
        self.assertIsNotNone(result["data"]["createdDatetime"])
