from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from rest_framework.exceptions import ValidationError

import logging
from openbook_common.utils.model_loaders import get_community_model, get_insight_model

from openbook_notifications.notifications import (
    SpaceMembershipRequestNotification,
    SpaceMembershipRequestApprovalUserNotification,
    SpaceMembershipRequestApprovalAdminNotification,
    SpaceMembershipRequestDeclineUserNotification,
    SpaceMembershipRequestDeclineAdminNotification,
    SpaceMembershipInviteNotification,
    SpaceMembershipInviteApprovalUserNotification,
    SpaceMembershipInviteApprovalAdminNotification,
    SpaceMembershipInviteDeclineUserNotification,
    SpaceMembershipInviteDeclineAdminNotification,
    PostCommentMentionNotification,
    PostCommentAuthorNotification,
    SpaceNewPostNotification,
    SpaceAppointmentCreationNotification,
    SpaceAppointmentUpdateNotification,
    SpaceAppointmentDeletionNotification,
    PollUpdatesNotification,
    CommentReactionNotification,
    PostReactionNotification,
    WelcomeEmailSeriesNotification,
)
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
    PollUpdatesPayload,
    PostReactionPayload,
    CommentReactionPayload,
    WelcomeEmailSeriesPayload,
)

from openbook_notifications.wrappers import skip_e2e_notifications

if TYPE_CHECKING:
    from openbook_auth.models import User
    from comments.models import Comment
    from openbook_appointments.models import Appointment
    from openbook_communities.models import CommunityInvite, CommunityMembershipRequest
    from openbook_communities.models import Community
    from openbook_polls.models import Poll

logger = logging.getLogger(__name__)


class NotificationsService:
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
    def _find_comment_commentable_context_id(comment: Comment):
        comment_target = comment.commentable_type.model

        if "feedpost" == comment_target:
            return None

        if "post" == comment_target:
            Community = get_community_model()
            space = Community.objects.filter(posts__id=comment.commentable_id).first()
            if not space:
                raise ValidationError("No community found for space post")

            return space.id

        if "discussion" == comment_target:
            Insight = get_insight_model()
            insight = Insight.objects.filter(discussions__id=comment.commentable_id).first()
            if not insight:
                raise ValidationError("No insight found for discussion")

            return insight.id

        raise ValidationError("Can not find context for comment commentable")

    @staticmethod
    def send_comment_mention_notification(comment: Comment):
        try:
            comment_commentable_context_id = NotificationsService._find_comment_commentable_context_id(comment)
            notification = PostCommentMentionNotification(
                mentions=[str(mentioned_user.username) for mentioned_user in comment.mentions.all()],
                payload=PostCommentMentionPayload(
                    comment=comment,
                    comment_commentable_context_id=comment_commentable_context_id,
                    notification_type=NotificationType.POST_COMMENT_MENTION.value,
                ),
            )
            notification.send()
        except ValidationError:
            logger.error("Comment Mention Notification cannot be send")

    @staticmethod
    def send_commentable_author_notification(comment: Comment):
        try:
            comment_commentable_context_id = NotificationsService._find_comment_commentable_context_id(comment)

            notification = PostCommentAuthorNotification(
                author=str(comment.commentable.creator.username),
                payload=PostCommentAuthorPayload(
                    comment=comment,
                    comment_commentable_context_id=comment_commentable_context_id,
                    notification_type=NotificationType.POST_COMMENT_AUTHOR.value,
                ),
            )
            notification.send()
        except ValidationError:
            logger.error("Commentable Author Notification cannot be send")

    @staticmethod
    def send_space_new_post_notification(post, collaborators: List[User]):
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
        location_changed: bool,
        date_time_changed: bool,
        recipients: List[User],
    ):
        notification = SpaceAppointmentUpdateNotification(
            recipients=[str(recipient.username) for recipient in recipients],
            payload=SpaceAppointmentUpdatePayload(
                space=space,
                appointment=appointment,
                location_changed=location_changed,
                date_time_changed=date_time_changed,
            ),
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

    @staticmethod
    def send_poll_updates_notification(
        poll: Poll,
        recipients: List[User],
    ):
        notification = PollUpdatesNotification(
            recipients=[str(recipient.username) for recipient in recipients],
            payload=PollUpdatesPayload(poll=poll),
        )
        notification.send()

    @staticmethod
    def send_post_reaction_notification(
        post,
        reactor: User,
        recipient: User,
    ):
        notification = PostReactionNotification(
            author=str(recipient.username),
            payload=PostReactionPayload(reactor=reactor, post=post),
        )
        notification.send()

    @staticmethod
    def send_comment_reaction_notification(
        comment: Comment,
        reactor: User,
        recipient: User,
    ):
        context_id = NotificationsService._find_comment_commentable_context_id(comment)
        notification = CommentReactionNotification(
            commenter=str(recipient.username),
            payload=CommentReactionPayload(reactor=reactor, comment=comment, context_id=context_id),
        )
        notification.send()

    @staticmethod
    @skip_e2e_notifications
    def send_welcome_email_series_notification(user: User, spaces, insights, token):
        notification = WelcomeEmailSeriesNotification(
            user=str(user.username),
            payload=WelcomeEmailSeriesPayload(user=user, spaces=spaces, insights=insights, token=token),
            token=token,
        )
        notification.send()
