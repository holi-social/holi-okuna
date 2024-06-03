from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from django.conf import settings

from openbook_notifications.helpers import replace_mentions_with_full_names

if TYPE_CHECKING:
    from openbook_auth.models import User
    from openbook_communities.models import Community
    from openbook_posts.models import Post
    from comments.models import Comment
    from openbook_appointments.models import Appointment
    from openbook_insights.models import Discussion
    from feed_posts.models import FeedPost


class NotificationType(Enum):
    SPACE_MEMBERSHIP_REQUEST = "SPACE_MEMBERSHIP_REQUEST"
    SPACE_MEMBERSHIP_REQUEST_APPROVAL_USER = "SPACE_MEMBERSHIP_REQUEST_APPROVAL_USER"
    SPACE_MEMBERSHIP_REQUEST_APPROVAL_ADMIN = "SPACE_MEMBERSHIP_REQUEST_APPROVAL_ADMIN"
    SPACE_MEMBERSHIP_REQUEST_DECLINE_USER = "SPACE_MEMBERSHIP_REQUEST_DECLINE_USER"
    SPACE_MEMBERSHIP_REQUEST_DECLINE_ADMIN = "SPACE_MEMBERSHIP_REQUEST_DECLINE_ADMIN"
    SPACE_MEMBERSHIP_INVITE = "SPACE_MEMBERSHIP_INVITE"
    SPACE_MEMBERSHIP_INVITE_APPROVAL_USER = "SPACE_MEMBERSHIP_INVITE_APPROVAL_USER"
    SPACE_MEMBERSHIP_INVITE_APPROVAL_ADMIN = "SPACE_MEMBERSHIP_INVITE_APPROVAL_ADMIN"
    SPACE_MEMBERSHIP_INVITE_DECLINE_USER = "SPACE_MEMBERSHIP_INVITE_DECLINE_USER"
    SPACE_MEMBERSHIP_INVITE_DECLINE_ADMIN = "SPACE_MEMBERSHIP_INVITE_DECLINE_ADMIN"
    POST_COMMENT_MENTION = "POST_COMMENT_MENTION"
    POST_COMMENT_AUTHOR = "POST_COMMENT_AUTHOR"
    SPACE_NEW_POST = "SPACE_NEW_POST"
    SPACE_APPOINTMENT_CREATION = "SPACE_APPOINTMENT_CREATION"
    SPACE_APPOINTMENT_UPDATE = "SPACE_APPOINTMENT_UPDATE"
    SPACE_APPOINTMENT_DELETION = "SPACE_APPOINTMENT_DELETION"


class UserData:
    def __init__(
        self,
        id: str,
        full_name: str,
        avatar_blurhash: Optional[str] = "",
        avatar_default_color: Optional[str] = "",
        avatar: Optional[str] = "",
        avatar_label: str = "",
    ):
        self.id = id
        self.full_name = full_name
        self.avatar = avatar
        self.avatar_blurhash = avatar_blurhash
        self.avatar_default_color = avatar_default_color
        self.avatar_label = avatar_label

    def to_dict(self):
        return {
            "id": self.id,
            "fullName": self.full_name,
            "avatar": self.avatar,
            "avatarBlurhash": self.avatar_blurhash,
            "avatarDefaultColor": self.avatar_default_color,
            "avatarLabel": self.avatar_label,
        }

    @classmethod
    def from_user(cls, user: User):
        return cls(
            id=str(user.username),
            full_name=user.profile.full_name(),
            avatar=user.profile.avatar.url if user.profile.avatar else "",
            avatar_blurhash=user.profile.avatar_blurhash if user.profile.avatar_blurhash else "",
            avatar_default_color=str(user.avatar_default_color) if user.avatar_default_color else "",
            avatar_label=user.avatar_label,
        )


class SpaceData:
    def __init__(
        self,
        id: str,
        title: str,
        name: str,
        avatar_blurhash: str = "",
        avatar_default_color: str = "",
        avatar: Optional[str] = "",
    ):
        self.id = id
        self.name = name
        self.title = title
        self.avatar = avatar
        self.avatar_blurhash = avatar_blurhash
        self.avatar_default_color = avatar_default_color

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "title": self.title,
            "avatar": self.avatar,
            "avatarBlurhash": self.avatar_blurhash,
            "avatarDefaultColor": self.avatar_default_color,
        }

    @classmethod
    def from_community(cls, community: Community):
        return cls(
            id=str(community.id),
            name=community.name,
            title=community.title,
            avatar=community.avatar.url if community.avatar else "",
            avatar_blurhash=community.avatar_blurhash if community.avatar_blurhash else "",
            avatar_default_color=str(community.avatar_default_color) if community.avatar_default_color else "",
        )


class AppointmentData:
    def __init__(
        self,
        id: str,
        title: str,
        description: str,
        location: str,
        start_date_time: datetime,
        end_date_time: datetime,
        start_date_time_utc: datetime,
        end_date_time_utc: datetime,
        timezone: str,
        starts_and_ends_on_same_day: bool,
    ):
        self.id = id
        self.title = title
        self.description = description
        self.location = location
        self.start_date_time = start_date_time
        self.end_date_time = end_date_time
        self.start_date_time_utc = start_date_time_utc
        self.end_date_time_utc = end_date_time_utc
        self.timezone = timezone
        self.starts_and_ends_on_same_day = starts_and_ends_on_same_day

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "location": self.location,
            "startDateTime": self.start_date_time,
            "endDateTime": self.end_date_time,
            "startDateTimeUTC": self.start_date_time_utc,
            "endDateTimeUTC": self.end_date_time_utc,
            "timezone": self.timezone,
            "startsAndEndsOnSameDay": self.starts_and_ends_on_same_day,
        }

    @classmethod
    def from_appointment(cls, appointment):
        start_date_time = appointment.start_date_time
        end_date_time = appointment.end_date_time

        start_date_time_utc = start_date_time.replace(tzinfo=None)
        end_date_time_utc = end_date_time.replace(tzinfo=None)

        utc_offset = start_date_time.utcoffset()

        # Convert the UTC offset to hours and format as GMT±H
        timezone = (
            "GMT"
            if utc_offset.total_seconds() == 0
            else f"GMT{'+' if utc_offset.total_seconds() >= 0 else '-'}{int(abs(utc_offset.total_seconds() // 3600))}"
        )

        return cls(
            id=str(appointment.id),
            title=appointment.title,
            description=appointment.description,
            location=appointment.location_details.complete_address if appointment.location_details else "",
            start_date_time=start_date_time.isoformat(),
            end_date_time=end_date_time.isoformat(),
            start_date_time_utc=start_date_time_utc.isoformat(),
            end_date_time_utc=end_date_time_utc.isoformat(),
            timezone=timezone,
            starts_and_ends_on_same_day=appointment.starts_and_ends_on_same_day,
        )


class CommentableData:
    def __init__(self, id: str, title: str, context: str, is_public: bool):
        self.id = id
        self.title = title
        self.context = context
        self.is_public = is_public

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "context": self.context,
            "isPublic": self.is_public,
        }

    @classmethod
    def from_commentable(cls, commentable: Post | FeedPost | Discussion):
        # some of the commentable models don't have those fields anymore
        # the notification templates can fall back to a generic body text in that case
        context = getattr(commentable, "context", None)
        title = getattr(commentable, "title", None)
        is_public = getattr(commentable, "is_public", False)

        return cls(
            id=str(commentable.id),
            title=title,
            context=context,
            is_public=is_public,
        )


class PostData:
    def __init__(self, id: str, title: str, context: str, is_public: bool):
        self.id = id
        self.title = title
        self.context = context
        self.is_public = is_public

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "context": self.context,
            "isPublic": self.is_public,
        }

    @classmethod
    def from_post(cls, post: Post):
        return cls(
            id=str(post.id),
            title=post.title if post.title else "",
            context=post.community.title,
            is_public=post.is_public,
        )


class CommentData:
    def __init__(self, id: str, text: str):
        self.id = id
        self.text = text

    def to_dict(self):
        return {"id": self.id, "text": self.text}

    @classmethod
    def from_comment(cls, comment: Comment):
        mentioned_users = comment.mentions.all()
        text = replace_mentions_with_full_names(text=comment.text, mentioned_users=mentioned_users)

        return cls(id=str(comment.id), text=text)

    @classmethod
    def create_link(cls, comment, comment_commentable_context_id):
        comment_target = comment.commentable_type.model

        if "feedpost" == comment_target:
            return f"/feed-posts/{comment.commentable_id}?commentId={comment.id}"

        if "post" == comment_target:
            return f"/spaces/{comment_commentable_context_id}/updates/{comment.commentable_id}?commentId={comment.id}"

        if "discussion" == comment_target:
            return f"/insights/{comment_commentable_context_id}/discussions/{comment.commentable_id}?commentId={comment.id}"

        # default to base url
        return f"{settings.APP_URL}"


class Payload:
    def __init__(self, data: dict, notification_type: str, notification_version: str):
        self.data = data
        self.notification_type = notification_type
        self.notification_version = notification_version

    def to_dict(self) -> dict:
        return {
            "data": self.data,
            "notificationType": self.notification_type,
            "notificationVersion": self.notification_version,
        }


class SpaceMembershipRequestPayload(Payload):
    NOTIFICATION_VERSION = "1.0.0"

    def __init__(self, user: User, space: Community, message: Optional[str] = ""):
        super().__init__(
            data={
                "user": UserData.from_user(user).to_dict(),
                "space": SpaceData.from_community(space).to_dict(),
                "requestMessage": message if message else "",
                "requestDatetime": datetime.now().isoformat(),
                "collaboratorsLink": f"{settings.APP_URL}/spaces/{space.name}/collaborators/manage?tab=pending&userId={user.username}",
            },
            notification_type=NotificationType.SPACE_MEMBERSHIP_REQUEST.value,
            notification_version=SpaceMembershipRequestPayload.NOTIFICATION_VERSION,
        )


class SpaceMembershipRequestApprovalUserPayload(Payload):
    NOTIFICATION_VERSION = "1.0.0"

    def __init__(self, user: User, space: Community, approver: User):
        super().__init__(
            data={
                "user": UserData.from_user(user).to_dict(),
                "space": SpaceData.from_community(space).to_dict(),
                "approver": UserData.from_user(approver).to_dict(),
                "approvalDatetime": datetime.now().isoformat(),
                "spaceLink": f"{settings.APP_URL}/spaces/{space.name}",
            },
            notification_type=NotificationType.SPACE_MEMBERSHIP_REQUEST_APPROVAL_USER.value,
            notification_version=SpaceMembershipRequestApprovalUserPayload.NOTIFICATION_VERSION,
        )


class SpaceMembershipRequestApprovalAdminPayload(Payload):
    NOTIFICATION_VERSION = "1.0.0"

    def __init__(self, user: User, space: Community):
        super().__init__(
            data={
                "user": UserData.from_user(user).to_dict(),
                "space": SpaceData.from_community(space).to_dict(),
            },
            notification_type=NotificationType.SPACE_MEMBERSHIP_REQUEST_APPROVAL_ADMIN.value,
            notification_version=SpaceMembershipRequestApprovalAdminPayload.NOTIFICATION_VERSION,
        )


class SpaceMembershipRequestDeclinePayload(Payload):
    NOTIFICATION_VERSION = "1.0.0"

    def __init__(self, user: User, space: Community, denier: User, notification_type: NotificationType):
        super().__init__(
            data={
                "user": UserData.from_user(user).to_dict(),
                "space": SpaceData.from_community(space).to_dict(),
                "denier": UserData.from_user(denier).to_dict(),
                "denialDatetime": datetime.now().isoformat(),
            },
            notification_type=notification_type,
            notification_version=SpaceMembershipRequestDeclinePayload.NOTIFICATION_VERSION,
        )


class SpaceMembershipInvitePayload(Payload):
    NOTIFICATION_VERSION = "1.0.0"

    def __init__(self, user: User, space: Community):
        super().__init__(
            data={
                "user": UserData.from_user(user).to_dict(),
                "space": SpaceData.from_community(space).to_dict(),
                "inviteDatetime": datetime.now().isoformat(),
            },
            notification_type=NotificationType.SPACE_MEMBERSHIP_INVITE.value,
            notification_version=SpaceMembershipInvitePayload.NOTIFICATION_VERSION,
        )


class SpaceMembershipInviteApprovalPayload(Payload):
    NOTIFICATION_VERSION = "1.0.0"

    def __init__(self, user: User, space: Community, notification_type: NotificationType):
        super().__init__(
            data={
                "user": UserData.from_user(user).to_dict(),
                "space": SpaceData.from_community(space).to_dict(),
            },
            notification_type=notification_type,
            notification_version=SpaceMembershipInviteApprovalPayload.NOTIFICATION_VERSION,
        )


class SpaceMembershipInviteDeclinePayload(Payload):
    NOTIFICATION_VERSION = "1.0.0"

    def __init__(self, user: User, space: Community, notification_type: NotificationType):
        super().__init__(
            data={
                "user": UserData.from_user(user).to_dict(),
                "space": SpaceData.from_community(space).to_dict(),
            },
            notification_type=notification_type,
            notification_version=SpaceMembershipInviteDeclinePayload.NOTIFICATION_VERSION,
        )


class PostCommentMentionPayload(Payload):
    NOTIFICATION_VERSION = "1.1.0"

    def __init__(
        self,
        comment: Comment,
        comment_commentable_context_id: str,
        notification_type: NotificationType,
    ):
        super().__init__(
            data={
                "user": UserData.from_user(comment.commenter).to_dict(),
                "comment": CommentData.from_comment(comment).to_dict(),
                "commentLink": CommentData.create_link(comment, comment_commentable_context_id),
                "commentDatetime": datetime.now().isoformat(),
                # have commentable context into post field, to keep the existing workflows and frontend parts happy
                "post": comment.commentable.comment_notification_context.to_dict(),
            },
            notification_type=notification_type,
            notification_version=PostCommentMentionPayload.NOTIFICATION_VERSION,
        )


class PostCommentAuthorPayload(Payload):
    NOTIFICATION_VERSION = "1.1.0"

    def __init__(
        self,
        comment: Comment,
        comment_commentable_context_id: str,
        notification_type: NotificationType,
    ):
        super().__init__(
            data={
                "user": UserData.from_user(comment.commentable.creator).to_dict(),
                "commenter": UserData.from_user(comment.commenter).to_dict(),
                "comment": CommentData.from_comment(comment).to_dict(),
                "commentLink": CommentData.create_link(comment, comment_commentable_context_id),
                "commentDatetime": datetime.now().isoformat(),
                # have commentable context into post field, to keep the existing workflows and frontend parts happy
                "post": comment.commentable.comment_notification_context.to_dict(),
            },
            notification_type=notification_type,
            notification_version=PostCommentAuthorPayload.NOTIFICATION_VERSION,
        )


class SpaceNewPostPayload(Payload):
    NOTIFICATION_VERSION = "1.0.0"

    def __init__(
        self,
        post: Post,
        notification_type: NotificationType,
    ):
        super().__init__(
            data={
                "user": UserData.from_user(post.creator).to_dict(),
                "post": PostData.from_post(post).to_dict(),
                "space": SpaceData.from_community(post.community).to_dict(),
                "createdDatetime": datetime.now().isoformat(),
            },
            notification_type=notification_type,
            notification_version=SpaceNewPostPayload.NOTIFICATION_VERSION,
        )


class SpaceAppointmentCreationPayload(Payload):
    NOTIFICATION_VERSION = "1.0.0"

    def __init__(self, space: Community, appointment: Appointment):
        super().__init__(
            data={
                "space": SpaceData.from_community(space).to_dict(),
                "appointment": AppointmentData.from_appointment(appointment).to_dict(),
                "link": f"{settings.APP_URL}/spaces/{space.name}/appointments/{appointment.slug}",
                "spaceLink": f"{settings.APP_URL}/spaces/{space.name}",
            },
            notification_type=NotificationType.SPACE_APPOINTMENT_CREATION.value,
            notification_version=SpaceAppointmentCreationPayload.NOTIFICATION_VERSION,
        )


class SpaceAppointmentUpdatePayload(Payload):
    NOTIFICATION_VERSION = "1.0.0"

    def __init__(self, space: Community, appointment: Appointment, location_changed: bool, date_time_changed: bool):
        super().__init__(
            data={
                "space": SpaceData.from_community(space).to_dict(),
                "appointment": AppointmentData.from_appointment(appointment).to_dict(),
                "locationChanged": location_changed,
                "dateTimeChanged": date_time_changed,
                "link": f"{settings.APP_URL}/spaces/{space.name}/appointments/{appointment.slug}",
                "spaceLink": f"{settings.APP_URL}/spaces/{space.name}",
            },
            notification_type=NotificationType.SPACE_APPOINTMENT_UPDATE.value,
            notification_version=SpaceAppointmentUpdatePayload.NOTIFICATION_VERSION,
        )


class SpaceAppointmentDeletionPayload(Payload):
    NOTIFICATION_VERSION = "1.0.0"

    def __init__(self, space: Community, appointment: Appointment):
        super().__init__(
            data={
                "space": SpaceData.from_community(space).to_dict(),
                "appointment": AppointmentData.from_appointment(appointment).to_dict(),
                "spaceLink": f"{settings.APP_URL}/spaces/{space.name}",
            },
            notification_type=NotificationType.SPACE_APPOINTMENT_DELETION.value,
            notification_version=SpaceAppointmentDeletionPayload.NOTIFICATION_VERSION,
        )
