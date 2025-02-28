from __future__ import annotations

import json
import uuid
from enum import Enum
from typing import List, Optional

import sentry_sdk
from novu.api import EventApi
from requests import Session
from requests.adapters import HTTPAdapter, Retry
from requests.exceptions import ConnectionError

from django.conf import settings

from openbook_notifications.payloads import (
    PostCommentAuthorPayload,
    PostCommentMentionPayload,
    SpaceAppointmentCreationPayload,
    SpaceAppointmentDeletionPayload,
    SpaceAppointmentUpdatePayload,
    SpaceMembershipInviteApprovalPayload,
    SpaceMembershipInviteDeclinePayload,
    SpaceMembershipInvitePayload,
    SpaceMembershipRequestApprovalAdminPayload,
    SpaceMembershipRequestApprovalUserPayload,
    SpaceMembershipRequestDeclinePayload,
    SpaceMembershipRequestPayload,
    SpaceNewPostPayload,
    PollUpdatesPayload,
    PostReactionPayload,
    CommentReactionPayload,
    WelcomeEmailSeriesPayload,
)

environment_id = settings.ENVIRONMENT_ID


class EmailIdentifier(Enum):
    DEV_SUPPORT_EMAIL = "DEV_SUPPORT_EMAIL"
    PROD_SUPPORT_EMAIL = "PROD_SUPPORT_EMAIL"


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
    POLL_UPDATES = "poll-updates"
    POST_REACTIONS = "post-reactions"
    COMMENT_REACTIONS = "comment-reactions"
    WELCOME_EMAIL_SERIES = "welcome-email-series"


# INTERNAL USE ONLY, use NotificationsService  to trigger notifications
class Notification:
    class DeliveryError(Exception):
        pass

    def __init__(
        self,
        workflow: str,
        recipients: str | List[str],
        payload: dict,
        transaction_id: str,
        email_identifier: EmailIdentifier = None,
    ):
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
        self.email_identifier = email_identifier

        # Android notifications only allow for key/value pairs in the data field to be of type string, not objects/JSON
        # (see https://firebase.google.com/docs/reference/fcm/rest/v1/projects.messages#androidconfig).
        # That is why we serialize the nested data object to a string and deserialize back to JSON it in the mobile client.
        android_payload = {k: v for k, v in payload.items() if not isinstance(v, dict)}
        android_payload["data"] = json.dumps(payload.get("data"))
        # iOS allows to use full JSON-serializable objects as payload
        # (see https://firebase.google.com/docs/reference/fcm/rest/v1/projects.messages#apnsconfig)
        self.overrides = {
            "type": "data",  # data notification
            "fcm": {"type": "notification", "data": android_payload},
            "apns": {"payload": payload},
        }

        if email_identifier:
            self.overrides["email"] = {"integrationIdentifier": email_identifier.value}

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
            sentry_sdk.capture_exception(
                Notification.DeliveryError("Error between Okuna and Novu while sending Notification")
            )
            return None
        except ConnectionError:
            # retries exceeded
            sentry_sdk.capture_exception(Notification.DeliveryError("Can't connect to Novu"))
            return None
        except Exception:
            sentry_sdk.capture_exception(Notification.DeliveryError("Novu SDK failed"))
            return None


class SpaceMembershipRequestNotification(Notification):
    def __init__(self, recipients: str | List[str], payload: SpaceMembershipRequestPayload, transaction_id: str):
        super().__init__(
            workflow=Workflow.SPACE_MEMBERSHIP_REQUEST.value,
            recipients=recipients,
            payload=payload.to_dict(),
            transaction_id=transaction_id,
        )


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


class SpaceMembershipInviteNotification(Notification):
    def __init__(self, recipient: str, payload: SpaceMembershipInvitePayload, transaction_id: str):
        super().__init__(
            workflow=Workflow.SPACE_MEMBERSHIP_INVITE.value,
            recipients=recipient,
            payload=payload.to_dict(),
            transaction_id=transaction_id,
        )


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


class PollUpdatesNotification(Notification):
    def __init__(
        self,
        recipients: List[str],
        payload: PollUpdatesPayload,
        transaction_id: Optional[str] = None,
    ):
        super().__init__(
            workflow=Workflow.POLL_UPDATES.value,
            recipients=recipients,
            payload=payload.to_dict(),
            transaction_id=transaction_id if transaction_id else str(uuid.uuid4()),
        )


class PostReactionNotification(Notification):
    def __init__(
        self,
        author: str,
        payload: PostReactionPayload,
        transaction_id: Optional[str] = None,
    ):
        super().__init__(
            workflow=Workflow.POST_REACTIONS.value,
            recipients=author,
            payload=payload.to_dict(),
            transaction_id=transaction_id if transaction_id else str(uuid.uuid4()),
        )


class CommentReactionNotification(Notification):
    def __init__(
        self,
        commenter: str,
        payload: CommentReactionPayload,
        transaction_id: Optional[str] = None,
    ):
        super().__init__(
            workflow=Workflow.COMMENT_REACTIONS.value,
            recipients=commenter,
            payload=payload.to_dict(),
            transaction_id=transaction_id if transaction_id else str(uuid.uuid4()),
        )


class WelcomeEmailSeriesNotification(Notification):
    def __init__(
        self,
        user: str,
        payload: WelcomeEmailSeriesPayload,
        token: str,
    ):
        super().__init__(
            workflow=Workflow.WELCOME_EMAIL_SERIES.value,
            recipients=user,
            payload=payload.to_dict(),
            transaction_id=token,  # token is used as transaction_id to cancel the workflow and unsubscribe the user from newsletter
            email_identifier=EmailIdentifier.PROD_SUPPORT_EMAIL
            if environment_id == "production"
            else EmailIdentifier.DEV_SUPPORT_EMAIL,
        )
