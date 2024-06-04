import uuid
from unittest import mock
from unittest.mock import patch

import pytest
import sentry_sdk
from django.test import TestCase
from novu.api import EventApi

from openbook_common.enums import FeatureToggleName, FeatureToggleType
from openbook_common.models import FeatureToggle as FeatureToggleModel
from openbook_common.tests.helpers import (
    make_community,
    make_community_post,
    make_space_post_comment,
    make_user,
)
from openbook_common.utils.model_loaders import get_community_model
from openbook_notifications.notifications import (
    Notification,
    PostCommentAuthorNotification,
    PostCommentMentionNotification,
    SpaceMembershipInviteApprovalAdminNotification,
    SpaceMembershipInviteApprovalUserNotification,
    SpaceMembershipInviteDeclineAdminNotification,
    SpaceMembershipInviteDeclineUserNotification,
    SpaceMembershipInviteNotification,
    SpaceMembershipRequestApprovalAdminNotification,
    SpaceMembershipRequestApprovalUserNotification,
    SpaceMembershipRequestDeclineAdminNotification,
    SpaceMembershipRequestDeclineUserNotification,
    SpaceMembershipRequestNotification,
    SpaceNewPostNotification,
    Workflow,
)
from openbook_notifications.payloads import (
    NotificationType,
    PostCommentAuthorPayload,
    PostCommentMentionPayload,
    SpaceMembershipInviteApprovalPayload,
    SpaceMembershipInviteDeclinePayload,
    SpaceMembershipInvitePayload,
    SpaceMembershipRequestApprovalAdminPayload,
    SpaceMembershipRequestApprovalUserPayload,
    SpaceMembershipRequestDeclinePayload,
    SpaceMembershipRequestPayload,
    SpaceNewPostPayload,
)


@pytest.fixture(scope="class", autouse=True)
def mock_novu_api():
    with mock.patch.object(EventApi, "trigger"):
        # prevent sending novu notifications
        yield


@pytest.mark.django_db
class NotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.notification_instance = Notification(
            workflow="test-workflow",
            recipients=["user-id"],
            payload={"data": {"key": "value"}},
            transaction_id="test-transaction-id",
        )
        cls.notifications_toggle = FeatureToggleModel.objects.create(
            name=FeatureToggleName.NOTIFICATIONS.value, status=FeatureToggleType.PRODUCTION
        )

        cls.overrides = {
            "type": "data",
            "fcm": {"type": "data", "data": {"key": "value"}},
            "apns": {"payload": {"data": {"key": "value"}}},
        }

    @patch.object(EventApi, "trigger")
    def test_notification_send(self, mock_event_api_trigger):
        result = self.notification_instance.send()

        # Assert that the EventApi trigger was called with the expected arguments
        mock_event_api_trigger.assert_called_with(
            name="test-workflow",
            recipients=["user-id"],
            payload={"data": {"key": "value"}},
            overrides=self.overrides,
            transaction_id="test-transaction-id",
        )

        self.assertEqual(result, mock_event_api_trigger.return_value)

    @patch.object(EventApi, "trigger")
    @patch.object(sentry_sdk, "capture_exception")
    def test_notification_delivery_fails_without_raising(self, mock_sentry_sdk_capture, mock_event_api_trigger):
        mock_event_api_trigger.side_effect = [ConnectionError("Novu down")]

        try:
            self.notification_instance.send()
        except:  # noqa: E722
            pytest.fail("Notification sending has not failed gracefully")

        assert mock_event_api_trigger.call_count == 1
        assert mock_sentry_sdk_capture.call_count == 1


@pytest.mark.django_db
class SpaceMembershipRequestNotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = make_user()
        space = make_community()
        transaction_id = str(uuid.uuid4())
        payload = SpaceMembershipRequestPayload(user=user, space=space)
        cls.notification_instance = SpaceMembershipRequestNotification(
            recipients=str(user.username),
            payload=payload,
            transaction_id=transaction_id,
        )

    def test_space_membership_request_notification_workflow(self):
        self.assertEqual(self.notification_instance.workflow, Workflow.SPACE_MEMBERSHIP_REQUEST.value)


@pytest.mark.django_db
class SpaceMembershipRequestApprovalUserNotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = make_user()
        approver = make_user()
        space = make_community()
        transaction_id = str(uuid.uuid4())
        payload = SpaceMembershipRequestApprovalUserPayload(user=user, space=space, approver=approver)
        cls.notification_instance = SpaceMembershipRequestApprovalUserNotification(
            recipient=str(user.username),
            payload=payload,
            transaction_id=transaction_id,
        )

    def test_space_membership_request_approval_user_notification_workflow(self):
        self.assertEqual(self.notification_instance.workflow, Workflow.SPACE_MEMBERSHIP_REQUEST_APPROVAL_USER.value)


@pytest.mark.django_db
class SpaceMembershipRequestApprovalAdminNotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = make_user()
        space = make_community()
        transaction_id = str(uuid.uuid4())
        payload = SpaceMembershipRequestApprovalAdminPayload(user=user, space=space)
        cls.notification_instance = SpaceMembershipRequestApprovalAdminNotification(
            recipients=str(user.username),
            payload=payload,
            transaction_id=transaction_id,
        )

    def test_space_membership_request_approval_admin_notification_workflow(self):
        self.assertEqual(self.notification_instance.workflow, Workflow.SPACE_MEMBERSHIP_REQUEST_APPROVAL_ADMIN.value)


class SpaceMembershipRequestDeclineUserNotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = make_user()
        denier = make_user()
        space = make_community()
        transaction_id = str(uuid.uuid4())
        payload = SpaceMembershipRequestDeclinePayload(
            user=user,
            space=space,
            denier=denier,
            notification_type=NotificationType.SPACE_MEMBERSHIP_REQUEST_DECLINE_USER.value,
        )
        cls.notification_instance = SpaceMembershipRequestDeclineUserNotification(
            recipient=str(user.username),
            payload=payload,
            transaction_id=transaction_id,
        )

    def test_space_membership_request_decline_user_notification_workflow(self):
        self.assertEqual(self.notification_instance.workflow, Workflow.SPACE_MEMBERSHIP_REQUEST_DECLINE_USER.value)


@pytest.mark.django_db
class SpaceMembershipRequestDeclineAdminNotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = make_user()
        denier = make_user()
        space = make_community()
        transaction_id = str(uuid.uuid4())
        payload = SpaceMembershipRequestDeclinePayload(
            user=user,
            space=space,
            denier=denier,
            notification_type=NotificationType.SPACE_MEMBERSHIP_REQUEST_DECLINE_ADMIN.value,
        )
        cls.notification_instance = SpaceMembershipRequestDeclineAdminNotification(
            recipients=[str(denier.username)],
            payload=payload,
            transaction_id=transaction_id,
        )

    def test_space_membership_request_decline_admin_notification_workflow(self):
        self.assertEqual(self.notification_instance.workflow, Workflow.SPACE_MEMBERSHIP_REQUEST_DECLINE_ADMIN.value)


@pytest.mark.django_db
class SpaceMembershipInviteNotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = make_user()
        space = make_community()
        transaction_id = str(uuid.uuid4())
        payload = SpaceMembershipInvitePayload(user=user, space=space)
        cls.notification_instance = SpaceMembershipInviteNotification(
            recipient=str(user.username),
            payload=payload,
            transaction_id=transaction_id,
        )

    def test_space_membership_invite_notification_workflow(self):
        self.assertEqual(self.notification_instance.workflow, Workflow.SPACE_MEMBERSHIP_INVITE.value)


@pytest.mark.django_db
class SpaceMembershipInviteApprovalUserNotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = make_user()
        space = make_community()
        transaction_id = str(uuid.uuid4())
        payload = SpaceMembershipInviteApprovalPayload(
            user=user,
            space=space,
            notification_type=NotificationType.SPACE_MEMBERSHIP_INVITE_APPROVAL_USER.value,
        )
        cls.notification_instance = SpaceMembershipInviteApprovalUserNotification(
            recipient=user.username,
            payload=payload,
            transaction_id=transaction_id,
        )

    def test_space_membership_invite_approval_user_notification_workflow(self):
        self.assertEqual(self.notification_instance.workflow, Workflow.SPACE_MEMBERSHIP_INVITE_APPROVAL_USER.value)


@pytest.mark.django_db
class SpaceMembershipInviteApprovalAdminNotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = make_user()
        space = make_community()
        transaction_id = str(uuid.uuid4())
        payload = SpaceMembershipInviteApprovalPayload(
            user=user,
            space=space,
            notification_type=NotificationType.SPACE_MEMBERSHIP_INVITE_APPROVAL_ADMIN.value,
        )
        cls.notification_instance = SpaceMembershipInviteApprovalAdminNotification(
            recipients=[str(space.creator.username)],
            payload=payload,
            transaction_id=transaction_id,
        )

    def test_space_membership_invite_approval_admin_notification_workflow(self):
        self.assertEqual(self.notification_instance.workflow, Workflow.SPACE_MEMBERSHIP_INVITE_APPROVAL_ADMIN.value)


@pytest.mark.django_db
class SpaceMembershipInviteDeclineUserNotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = make_user()
        space = make_community()
        transaction_id = str(uuid.uuid4())
        payload = SpaceMembershipInviteDeclinePayload(
            user=user,
            space=space,
            notification_type=NotificationType.SPACE_MEMBERSHIP_INVITE_DECLINE_USER.value,
        )
        cls.notification_instance = SpaceMembershipInviteDeclineUserNotification(
            recipient=user.username,
            payload=payload,
            transaction_id=transaction_id,
        )

    def test_space_membership_invite_decline_user_notification_workflow(self):
        self.assertEqual(self.notification_instance.workflow, Workflow.SPACE_MEMBERSHIP_INVITE_DECLINE_USER.value)


@pytest.mark.django_db
class SpaceMembershipInviteDeclineAdminNotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = make_user()
        space = make_community()
        transaction_id = str(uuid.uuid4())
        payload = SpaceMembershipInviteDeclinePayload(
            user=user,
            space=space,
            notification_type=NotificationType.SPACE_MEMBERSHIP_INVITE_DECLINE_ADMIN.value,
        )
        cls.notification_instance = SpaceMembershipInviteDeclineAdminNotification(
            recipient=space.creator.username,
            payload=payload,
            transaction_id=transaction_id,
        )

    def test_space_membership_invite_decline_admin_notification_workflow(self):
        self.assertEqual(self.notification_instance.workflow, Workflow.SPACE_MEMBERSHIP_INVITE_DECLINE_ADMIN.value)


@pytest.mark.django_db
class PostCommentMentionNotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        post_comment = make_space_post_comment()
        transaction_id = str(uuid.uuid4())
        payload = PostCommentMentionPayload(
            comment=post_comment,
            comment_commentable_context_id="someSpaceId",
            notification_type=NotificationType.POST_COMMENT_MENTION.value,
        )
        cls.notification_instance = PostCommentMentionNotification(
            mentions=[str(mention.username) for mention in post_comment.mentions.all()],
            payload=payload,
            transaction_id=transaction_id,
        )

    def test_post_comment_mention_notification_workflow(self):
        self.assertEqual(self.notification_instance.workflow, Workflow.POST_COMMENT_MENTION.value)


@pytest.mark.django_db
class PostCommentAuthorNotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        post_comment = make_space_post_comment()
        transaction_id = str(uuid.uuid4())
        payload = PostCommentAuthorPayload(
            comment=post_comment,
            comment_commentable_context_id="someSpaceId",
            notification_type=NotificationType.POST_COMMENT_AUTHOR.value,
        )
        cls.notification_instance = PostCommentAuthorNotification(
            author=str(post_comment.commentable.creator.username),
            payload=payload,
            transaction_id=transaction_id,
        )

    def test_post_comment_author_notification_workflow(self):
        self.assertEqual(self.notification_instance.workflow, Workflow.POST_COMMENT_AUTHOR.value)


@pytest.mark.django_db
class SpaceNewPostNotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        post = make_community_post()
        transaction_id = str(uuid.uuid4())

        payload = SpaceNewPostPayload(
            post=post,
            notification_type=NotificationType.SPACE_NEW_POST.value,
        )

        community_model = get_community_model()
        collaborators = community_model.get_community_with_name_members(community_name=post.community.name).exclude(
            id=post.creator.id
        )

        cls.notification_instance = SpaceNewPostNotification(
            collaborators=[str(collaborator.username) for collaborator in collaborators],
            payload=payload,
            transaction_id=transaction_id,
        )

    def test_space_new_post_workflow(self):
        self.assertEqual(self.notification_instance.workflow, Workflow.SPACE_NEW_POST.value)
