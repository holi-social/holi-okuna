import uuid
from enum import Enum
from typing import List
from typing import Optional

import sentry_sdk
from novu.api import EventApi
from requests import Session
from requests.adapters import HTTPAdapter, Retry
from requests.exceptions import ConnectionError

from openbook_appointments.models import Appointment
from openbook_auth.models import User
from openbook_communities.models import Community, CommunityMembershipRequest, CommunityInvite
from openbook_notifications.helpers import flatten_payload
from openbook_notifications.payloads import (
    SpaceMembershipRequestPayload,
    SpaceMembershipRequestApprovalUserPayload,
    SpaceMembershipRequestApprovalAdminPayload,
    SpaceMembershipRequestDeclinePayload,
    NotificationType,
    SpaceMembershipInvitePayload,
    SpaceMembershipInviteApprovalPayload,
    SpaceMembershipInviteDeclinePayload,
    PostCommentMentionPayload,
    PostCommentAuthorPayload,
    SpaceNewPostPayload,
    SpaceAppointmentCreationPayload,
    SpaceAppointmentUpdatePayload,
    SpaceAppointmentDeletionPayload,
)
from openbook_notifications.toggles import notifications_toggle
from openbook_posts.models import Post, PostComment


class Workflow(Enum):
    SPACE_MEMBERSHIP_REQUEST = "space-membership-request"
    SPACE_MEMBERSHIP_REQUEST_APPROVAL_USER = "space-membership-request-approval-user"
    SPACE_MEMBERSHIP_REQUEST_APPROVAL_ADMIN = "space-membership-request-approval-admin"
    SPACE_MEMBERSHIP_REQUEST_DECLINE_USER = "space-membership-request-decline-user"
    SPACE_MEMBERSHIP_REQUEST_DECLINE_ADMIN = "space-membership-request-decline-admin"
    SPACE_MEMBERSHIP_INVITE = "space-membership-invite"
    SPACE_MEMBERSHIP_INVITE_APPROVAL_USER = "space-membership-invite-approval-user"
    SPACE_MEMBERSHIP_INVITE_APPROVAL_ADMIN = "space-membership-invite-approval-admin"
    SPACE_MEMBERSHIP_INVITE_DECLINE_USER = "space-membership-invite-decline-user"
    SPACE_MEMBERSHIP_INVITE_DECLINE_ADMIN = "space-membership-invite-decline-admin"
    POST_COMMENT_MENTION = "post-comment-mention"
    POST_COMMENT_AUTHOR = "post-comment-author"
    SPACE_NEW_POST = "space-new-post"
    SPACE_APPOINTMENT_CREATION = "space-appointment-creation"
    SPACE_APPOINTMENT_UPDATE = "space-appointment-update"
    SPACE_APPOINTMENT_DELETION = "space-appointment-deletion"


# Use this classes static methods to trigger notifications via the Notifications system (novu)
# To avoid circular import issues (due to usage of domain classes here such as User) import deferred in method bodies
class Notifications:
    @staticmethod
    def send_space_membership_request_notification(
        membership_request: CommunityMembershipRequest,
        recipients: User | List[User],
        requester: User,
        space: Community,
        message: Optional[str] = "",
    ):
        notification = SpaceMembershipRequestNotification(
            recipients=[str(recipient.username) for recipient in recipients],
            payload=SpaceMembershipRequestPayload(space=space, user=requester, message=message),
            transaction_id=str(membership_request.id),
        )
        notification.send()

    @staticmethod
    def send_space_membership_request_approval_user_notification(
        requester: User,
        space: Community,
        approver: User,
    ):
        notification = SpaceMembershipRequestApprovalUserNotification(
            recipient=requester.username,
            payload=SpaceMembershipRequestApprovalUserPayload(user=requester, space=space, approver=approver),
        )
        notification.send()

    @staticmethod
    def send_space_membership_request_approval_admin_notification(
        recipients: User | List[User],
        requester: User,
        space: Community,
    ):
        notification = SpaceMembershipRequestApprovalAdminNotification(
            recipients=[str(recipient.username) for recipient in recipients],
            payload=SpaceMembershipRequestApprovalAdminPayload(user=requester, space=space),
        )
        notification.send()

    @staticmethod
    def send_space_membership_request_decline_user_notification(
        requester: User,
        space: Community,
        denier: User,
    ):
        notification = SpaceMembershipRequestDeclineUserNotification(
            recipient=requester.username,
            payload=SpaceMembershipRequestDeclinePayload(
                user=requester,
                space=space,
                denier=denier,
                notification_type=NotificationType.SPACE_MEMBERSHIP_REQUEST_DECLINE_USER.value,
            ),
        )
        notification.send()

    @staticmethod
    def send_space_membership_request_decline_admin_notification(
        recipients: User | List[User],
        requester: User,
        space: Community,
        denier: User,
    ):
        notification = SpaceMembershipRequestDeclineAdminNotification(
            recipients=[str(recipient.username) for recipient in recipients],
            payload=SpaceMembershipRequestDeclinePayload(
                user=requester,
                space=space,
                denier=denier,
                notification_type=NotificationType.SPACE_MEMBERSHIP_REQUEST_DECLINE_ADMIN.value,
            ),
        )
        notification.send()

    @staticmethod
    def send_space_membership_invite_notification(
        community_invite: CommunityInvite,
        recipient: User,
        inviter: User,
        space: Community,
    ):
        notification = SpaceMembershipInviteNotification(
            recipient=str(recipient.username),
            payload=SpaceMembershipInvitePayload(user=inviter, space=space),
            transaction_id=str(community_invite.id),
        )
        notification.send()

    @staticmethod
    def send_space_membership_invite_approval_user_notification(
        invitee: User,
        space: Community,
    ):
        notification = SpaceMembershipInviteApprovalUserNotification(
            recipient=invitee.username,
            payload=SpaceMembershipInviteApprovalPayload(
                user=invitee,
                space=space,
                notification_type=NotificationType.SPACE_MEMBERSHIP_INVITE_APPROVAL_USER.value,
            ),
        )
        notification.send()

    @staticmethod
    def send_space_membership_invite_approval_admin_notification(
        recipients: User | List[User],
        invitee: User,
        space: Community,
    ):
        notification = SpaceMembershipInviteApprovalAdminNotification(
            recipients=[str(recipient.username) for recipient in recipients],
            payload=SpaceMembershipInviteApprovalPayload(
                user=invitee,
                space=space,
                notification_type=NotificationType.SPACE_MEMBERSHIP_INVITE_APPROVAL_ADMIN.value,
            ),
        )
        notification.send()

    @staticmethod
    def send_space_membership_invite_decline_user_notification(
        invitee: User,
        space: Community,
    ):
        notification = SpaceMembershipInviteDeclineUserNotification(
            recipient=invitee.username,
            payload=SpaceMembershipInviteDeclinePayload(
                user=invitee,
                space=space,
                notification_type=NotificationType.SPACE_MEMBERSHIP_INVITE_DECLINE_USER.value,
            ),
        )
        notification.send()

    @staticmethod
    def send_space_membership_invite_decline_admin_notification(
        recipient: User,
        invitee: User,
        space: Community,
    ):
        notification = SpaceMembershipInviteDeclineAdminNotification(
            recipient=recipient.username,
            payload=SpaceMembershipInviteDeclinePayload(
                user=invitee,
                space=space,
                notification_type=NotificationType.SPACE_MEMBERSHIP_INVITE_DECLINE_ADMIN.value,
            ),
        )
        notification.send()

    @staticmethod
    def send_post_comment_mention_notification(post_comment: PostComment):
        notification = PostCommentMentionNotification(
            mentions=[str(mentioned_user.username) for mentioned_user in post_comment.mentions.all()],
            payload=PostCommentMentionPayload(
                post_comment=post_comment,
                notification_type=NotificationType.POST_COMMENT_MENTION.value,
            ),
        )
        notification.send()

    @staticmethod
    def send_post_comment_author_notification(post_comment: PostComment):
        notification = PostCommentAuthorNotification(
            author=str(post_comment.post.creator.username),
            payload=PostCommentAuthorPayload(
                post_comment=post_comment,
                notification_type=NotificationType.POST_COMMENT_AUTHOR.value,
            ),
        )
        notification.send()

    @staticmethod
    def send_space_new_post_notification(post: Post, collaborators: List[User]):
        notification = SpaceNewPostNotification(
            collaborators=[str(collaborator.username) for collaborator in collaborators],
            payload=SpaceNewPostPayload(
                post=post,
                notification_type=NotificationType.SPACE_NEW_POST.value,
            ),
        )
        notification.send()

    @staticmethod
    def send_space_appointment_creation_notification(
        space: Community,
        appointment: Appointment,
        recipients: List[User],
    ):
        notification = SpaceAppointmentCreationNotification(
            recipients=[str(recipient.username) for recipient in recipients],
            payload=SpaceAppointmentCreationPayload(space=space, appointment=appointment),
        )
        notification.send()

    @staticmethod
    def send_space_appointment_update_notification(
        space: Community,
        appointment: Appointment,
        recipients: List[User],
    ):
        notification = SpaceAppointmentUpdateNotification(
            recipients=[str(recipient.username) for recipient in recipients],
            payload=SpaceAppointmentUpdatePayload(space=space, appointment=appointment),
        )

        notification.send()

    @staticmethod
    def send_space_appointment_deletion_notification(
        space: Community,
        appointment: Appointment,
        recipients: List[User],
    ):
        notification = SpaceAppointmentDeletionNotification(
            recipients=[str(recipient.username) for recipient in recipients],
            payload=SpaceAppointmentDeletionPayload(space=space, appointment=appointment),
        )
        notification.send()


# INTERNAL USE ONLY, use Notifications instead to trigger notifications
class Notification:
    class DeliveryError(Exception):
        pass

    def __init__(self, workflow: str, recipients: str | List[str], payload: dict, transaction_id: str):
        session = Session()
        retries = Retry(
            total=3,
            backoff_factor=0.1,
            status_forcelist=[502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)

        self.workflow = workflow
        self.recipients = recipients
        self.payload = payload
        self.session = session
        self.transaction_id = transaction_id

        self.overrides = {
            "type": "data",  # data notification
            "fcm": {"type": "data", "data": flatten_payload(payload)},
            "apns": {"payload": payload},
        }

    @notifications_toggle
    def send(self):
        if not self.recipients:
            return

        try:
            return EventApi(session=self.session).trigger(
                name=self.workflow,
                recipients=self.recipients,
                payload=self.payload,
                overrides=self.overrides,
                transaction_id=self.transaction_id,
            )
        except TypeError:
            # Novu sdk raises a type error when a workflow is inactive
            # as the response does not contain a transaction_id but its response model requires it
            return None
        except ConnectionError:
            # retries exceeded
            sentry_sdk.capture_exception(Notification.DeliveryError("Can't connect to Novu"))
            return None
        except (Exception,) as e:
            sentry_sdk.capture_exception(Notification.DeliveryError("Novu SDK failed"))
            return None


# INTERNAL USE ONLY, use Notifications instead to trigger notifications
class SpaceMembershipRequestNotification(Notification):
    def __init__(self, recipients: str | List[str], payload: SpaceMembershipRequestPayload, transaction_id: str):
        super().__init__(
            workflow=Workflow.SPACE_MEMBERSHIP_REQUEST.value,
            recipients=recipients,
            payload=payload.to_dict(),
            transaction_id=transaction_id,
        )


# INTERNAL USE ONLY, use Notifications instead to trigger notifications
class SpaceMembershipRequestApprovalUserNotification(Notification):
    def __init__(
        self, recipient: str, payload: SpaceMembershipRequestApprovalUserPayload, transaction_id: Optional[str] = None
    ):
        super().__init__(
            workflow=Workflow.SPACE_MEMBERSHIP_REQUEST_APPROVAL_USER.value,
            recipients=recipient,
            payload=payload.to_dict(),
            transaction_id=transaction_id if transaction_id else str(uuid.uuid4()),
        )


class SpaceMembershipRequestApprovalAdminNotification(Notification):
    def __init__(
        self,
        recipients: str | List[str],
        payload: SpaceMembershipRequestApprovalAdminPayload,
        transaction_id: Optional[str] = None,
    ):
        super().__init__(
            workflow=Workflow.SPACE_MEMBERSHIP_REQUEST_APPROVAL_ADMIN.value,
            recipients=recipients,
            payload=payload.to_dict(),
            transaction_id=transaction_id if transaction_id else str(uuid.uuid4()),
        )


# INTERNAL USE ONLY, use Notifications instead to trigger notifications
class SpaceMembershipRequestDeclineUserNotification(Notification):
    def __init__(
        self, recipient: str, payload: SpaceMembershipRequestDeclinePayload, transaction_id: str | None = None
    ):
        super().__init__(
            workflow=Workflow.SPACE_MEMBERSHIP_REQUEST_DECLINE_USER.value,
            recipients=recipient,
            payload=payload.to_dict(),
            transaction_id=transaction_id if transaction_id else str(uuid.uuid4()),
        )


# INTERNAL USE ONLY, use Notifications instead to trigger notifications
class SpaceMembershipRequestDeclineAdminNotification(Notification):
    def __init__(
        self,
        recipients: str | List[str],
        payload: SpaceMembershipRequestDeclinePayload,
        transaction_id: str | None = None,
    ):
        super().__init__(
            workflow=Workflow.SPACE_MEMBERSHIP_REQUEST_DECLINE_ADMIN.value,
            recipients=recipients,
            payload=payload.to_dict(),
            transaction_id=transaction_id if transaction_id else str(uuid.uuid4()),
        )


# INTERNAL USE ONLY, use Notifications instead to trigger notifications
class SpaceMembershipInviteNotification(Notification):
    def __init__(self, recipient: str, payload: SpaceMembershipInvitePayload, transaction_id: str):
        super().__init__(
            workflow=Workflow.SPACE_MEMBERSHIP_INVITE.value,
            recipients=recipient,
            payload=payload.to_dict(),
            transaction_id=transaction_id,
        )


# INTERNAL USE ONLY, use Notifications instead to trigger notifications
class SpaceMembershipInviteApprovalUserNotification(Notification):
    def __init__(
        self,
        recipient: str,
        payload: SpaceMembershipInviteApprovalPayload,
        transaction_id: str | None = None,
    ):
        super().__init__(
            workflow=Workflow.SPACE_MEMBERSHIP_INVITE_APPROVAL_USER.value,
            recipients=recipient,
            payload=payload.to_dict(),
            transaction_id=transaction_id if transaction_id else str(uuid.uuid4()),
        )


# INTERNAL USE ONLY, use Notifications instead to trigger notifications
class SpaceMembershipInviteApprovalAdminNotification(Notification):
    def __init__(
        self,
        recipients: str | List[str],
        payload: SpaceMembershipInviteApprovalPayload,
        transaction_id: str | None = None,
    ):
        super().__init__(
            workflow=Workflow.SPACE_MEMBERSHIP_INVITE_APPROVAL_ADMIN.value,
            recipients=recipients,
            payload=payload.to_dict(),
            transaction_id=transaction_id if transaction_id else str(uuid.uuid4()),
        )


# INTERNAL USE ONLY, use Notifications instead to trigger notifications
class SpaceMembershipInviteDeclineUserNotification(Notification):
    def __init__(
        self,
        recipient: str,
        payload: SpaceMembershipInviteDeclinePayload,
        transaction_id: str | None = None,
    ):
        super().__init__(
            workflow=Workflow.SPACE_MEMBERSHIP_INVITE_DECLINE_USER.value,
            recipients=recipient,
            payload=payload.to_dict(),
            transaction_id=transaction_id if transaction_id else str(uuid.uuid4()),
        )


# INTERNAL USE ONLY, use Notifications instead to trigger notifications
class SpaceMembershipInviteDeclineAdminNotification(Notification):
    def __init__(
        self,
        recipient: str,
        payload: SpaceMembershipInviteDeclinePayload,
        transaction_id: str | None = None,
    ):
        super().__init__(
            workflow=Workflow.SPACE_MEMBERSHIP_INVITE_DECLINE_ADMIN.value,
            recipients=recipient,
            payload=payload.to_dict(),
            transaction_id=transaction_id if transaction_id else str(uuid.uuid4()),
        )


# INTERNAL USE ONLY, use Notifications instead to trigger notifications
class PostCommentMentionNotification(Notification):
    def __init__(
        self,
        mentions: List[str],
        payload: PostCommentMentionPayload,
        transaction_id: Optional[str] = None,
    ):
        super().__init__(
            workflow=Workflow.POST_COMMENT_MENTION.value,
            recipients=mentions,
            payload=payload.to_dict(),
            transaction_id=transaction_id if transaction_id else str(uuid.uuid4()),
        )


# INTERNAL USE ONLY, use Notifications instead to trigger notifications
class PostCommentAuthorNotification(Notification):
    def __init__(
        self,
        author: str,
        payload: PostCommentAuthorPayload,
        transaction_id: Optional[str] = None,
    ):
        super().__init__(
            workflow=Workflow.POST_COMMENT_AUTHOR.value,
            recipients=author,
            payload=payload.to_dict(),
            transaction_id=transaction_id if transaction_id else str(uuid.uuid4()),
        )


# INTERNAL USE ONLY, use Notifications instead to trigger notifications
class SpaceNewPostNotification(Notification):
    def __init__(
        self,
        collaborators: List[str],
        payload: SpaceNewPostPayload,
        transaction_id: Optional[str] = None,
    ):
        super().__init__(
            workflow=Workflow.SPACE_NEW_POST.value,
            recipients=collaborators,
            payload=payload.to_dict(),
            transaction_id=transaction_id if transaction_id else str(uuid.uuid4()),
        )


class SpaceAppointmentCreationNotification(Notification):
    def __init__(
        self,
        recipients: List[str],
        payload: SpaceAppointmentCreationPayload,
        transaction_id: Optional[str] = None,
    ):
        super().__init__(
            workflow=Workflow.SPACE_APPOINTMENT_CREATION.value,
            recipients=recipients,
            payload=payload.to_dict(),
            transaction_id=transaction_id if transaction_id else str(uuid.uuid4()),
        )


class SpaceAppointmentUpdateNotification(Notification):
    def __init__(
        self,
        recipients: List[str],
        payload: SpaceAppointmentUpdatePayload,
        transaction_id: Optional[str] = None,
    ):
        super().__init__(
            workflow=Workflow.SPACE_APPOINTMENT_UPDATE.value,
            recipients=recipients,
            payload=payload.to_dict(),
            transaction_id=transaction_id if transaction_id else str(uuid.uuid4()),
        )


class SpaceAppointmentDeletionNotification(Notification):
    def __init__(
        self,
        recipients: List[str],
        payload: SpaceAppointmentDeletionPayload,
        transaction_id: Optional[str] = None,
    ):
        super().__init__(
            workflow=Workflow.SPACE_APPOINTMENT_DELETION.value,
            recipients=recipients,
            payload=payload.to_dict(),
            transaction_id=transaction_id if transaction_id else str(uuid.uuid4()),
        )
