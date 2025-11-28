from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional
import logging

from django.conf import settings

from openbook_common.utils.model_loaders import get_feed_post_model
from openbook_notifications.helpers import replace_mentions_with_full_names

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from openbook_auth.models import User
    from openbook_communities.models import Community
    from comments.models import Comment
    from openbook_appointments.models import Appointment
    from openbook_polls.models import Poll


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
    POLL_UPDATES = "POLL_UPDATES"
    POST_REACTION = "POST_REACTION"
    COMMENT_REACTION = "COMMENT_REACTION"
    POLL_CLOSURE = "POLL_CLOSURE"
    WELCOME_EMAIL_SERIES = "WELCOME_EMAIL_SERIES"


app_url = settings.APP_URL


class UserData:
    def __init__(
        self,
        id: str,
        full_name: str,
        profile_link: str,
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
        self.profile_link = profile_link

    def to_dict(self):
        return {
            "id": self.id,
            "fullName": self.full_name,
            "avatar": self.avatar,
            "avatarBlurhash": self.avatar_blurhash,
            "avatarDefaultColor": self.avatar_default_color,
            "avatarLabel": self.avatar_label,
            "profileLink": self.profile_link,
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
            profile_link=f"{app_url}/profile/{user.username}",
        )


class SpaceData:
    def __init__(
        self,
        id: str,
        title: str,
        name: str,
        goal: str,
        link: str,
        cover: str,
        avatar_blurhash: str = "",
        avatar_default_color: str = "",
        avatar: Optional[str] = "",
    ):
        self.id = id
        self.name = name
        self.title = title
        self.goal = goal
        self.avatar = avatar
        self.avatar_blurhash = avatar_blurhash
        self.avatar_default_color = avatar_default_color
        self.link = link
        self.cover = cover

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "title": self.title,
            "goal": self.goal,
            "avatar": self.avatar,
            "avatarBlurhash": self.avatar_blurhash,
            "avatarDefaultColor": self.avatar_default_color,
            "link": self.link,
            "cover": self.cover,
        }

    @classmethod
    def from_community(cls, community: Community):
        return cls(
            id=str(community.id),
            name=community.name,
            title=community.title,
            goal=community.description,
            avatar=community.avatar.url if community.avatar else "",
            avatar_blurhash=community.avatar_blurhash if community.avatar_blurhash else "",
            avatar_default_color=str(community.avatar_default_color) if community.avatar_default_color else "",
            link=f"{app_url}/spaces/{community.name}",
            cover=community.cover.url if community.cover else "",
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


class PostData:
    def __init__(
        self, id: str, title: str, text: str = None, community=None, is_public: bool = None, description: str = None
    ):
        self.id = id
        self.title = title
        self.text = text
        self.community = community
        self.is_public = is_public
        self.description = description

    def to_dict(self):
        data = {
            "id": self.id,
            "title": self.title,
        }
        if self.text:
            data["text"] = self.text
        if self.community:
            data["context"] = self.community.title
            data["link"] = f"/spaces/{self.community.id}/updates/{self.id}"
        else:
            data["link"] = f"/feed-posts/{self.id}"
        if self.description:
            data["description"] = self.description
        if self.is_public:
            data["isPublic"] = self.is_public
        return data

    @classmethod
    def from_post(cls, post):
        return cls(
            id=str(post.id),
            title=post.title if post.title else "",
            text=post.text if hasattr(post, "text") else None,
            community=post.community if hasattr(post, "community") else None,
            is_public=post.is_public if hasattr(post, "is_public") else None,
            description=post.description if hasattr(post, "description") else None,
        )


class InsightData:
    def __init__(
        self,
        id: str,
        title: str,
        cover: str,
        link: str,
    ):
        self.id = id
        self.title = title
        self.cover = cover
        self.link = link

    def to_dict(self):
        data = {
            "id": self.id,
            "title": self.title,
            "cover": self.cover,
            "link": self.link,
        }
        return data

    @classmethod
    def from_insight(cls, insight):
        return cls(
            id=str(insight.id),
            title=insight.title,
            cover=insight.header_image.url,
            link=f"{app_url}/insights/{insight.id}",
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
            if comment.parent_comment_id is not None:
                return f"/feed-posts/{comment.commentable_id}?commentId={comment.parent_comment_id}"
            return f"/feed-posts/{comment.commentable_id}?commentId={comment.id}"

        if "post" == comment_target:
            return f"/spaces/{comment_commentable_context_id}/updates/{comment.commentable_id}?commentId={comment.id}"

        if "discussion" == comment_target:
            return f"/insights/{comment_commentable_context_id}/discussions/{comment.commentable_id}?commentId={comment.id}"

        # default to base url
        return f"{settings.APP_URL}"


class PollData:
    def __init__(self, id: str, title: str, insight_id: Optional[str] = None, feed_post_id: Optional[str] = None):
        self.id = id
        self.title = title
        self.insight_id = insight_id
        self.feed_post_id = feed_post_id

    def to_dict(self):
        return {"id": self.id, "title": self.title, "insightId": self.insight_id, "feedPostId": self.feed_post_id}

    @classmethod
    def from_poll(cls, poll: Poll):
        # TODO: Update the following line when the relationship between insight and post
        #  changes from many-to-many to one-to-many.
        FeedPost = get_feed_post_model()
        insight = poll.insights.first()

        feed_post = FeedPost.objects.filter(poll=poll).first()

        truncated_title = poll.question_text

        if len(truncated_title) > 40:
            truncated_title = truncated_title[:40] + "..."

        return cls(
            id=str(poll.id),
            title=truncated_title,
            insight_id=str(insight.id) if insight else "",
            feed_post_id=str(feed_post.id) if feed_post else "",
        )


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
        post,
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


class PollUpdatesPayload(Payload):
    NOTIFICATION_VERSION = "1.0.0"

    def __init__(self, poll: Poll):
        super().__init__(
            data={
                "poll": PollData.from_poll(poll).to_dict(),
            },
            notification_type=NotificationType.POLL_UPDATES.value,
            notification_version=PollUpdatesPayload.NOTIFICATION_VERSION,
        )


class PollClosurePayload(Payload):
    NOTIFICATION_VERSION = "1.0.0"

    def __init__(self, poll: Poll):
        super().__init__(
            data={
                "poll": PollData.from_poll(poll).to_dict(),
            },
            notification_type=NotificationType.POLL_CLOSURE.value,
            notification_version=PollClosurePayload.NOTIFICATION_VERSION,
        )


class PostReactionPayload(Payload):
    NOTIFICATION_VERSION = "1.0.0"

    def __init__(self, reactor: User, post):
        super().__init__(
            data={
                "user": UserData.from_user(reactor).to_dict(),
                "post": PostData.from_post(post).to_dict(),
            },
            notification_type=NotificationType.POST_REACTION.value,
            notification_version=PostReactionPayload.NOTIFICATION_VERSION,
        )


class CommentReactionPayload(Payload):
    NOTIFICATION_VERSION = "1.0.0"

    def __init__(self, reactor: User, comment: Comment, context_id: str):
        comment_dict = CommentData.from_comment(comment).to_dict()
        comment_dict["link"] = CommentData.create_link(comment, context_id)
        super().__init__(
            data={
                "user": UserData.from_user(reactor).to_dict(),
                "comment": comment_dict,
            },
            notification_type=NotificationType.COMMENT_REACTION.value,
            notification_version=CommentReactionPayload.NOTIFICATION_VERSION,
        )


class WelcomeEmailSeriesPayload(Payload):
    NOTIFICATION_VERSION = "1.0.0"

    def __init__(self, user: User, token: str):
        super().__init__(
            data={
                "user": UserData.from_user(user).to_dict(),
                "unsubscribeUrl": f"{app_url}/unsubscribe?series=welcome&email={user.email}&token={token}",
            },
            notification_type=NotificationType.WELCOME_EMAIL_SERIES.value,
            notification_version=WelcomeEmailSeriesPayload.NOTIFICATION_VERSION,
        )
