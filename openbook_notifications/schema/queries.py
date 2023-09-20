import strawberry
import strawberry_django

from openbook_common.schema.types import Paged
from openbook_notifications.models import Notification as NotificationModel
from openbook_notifications.schema.types import NewNotificationsResponse, Notification

PUBLISHED_NOTIFICATION_TYPES = [
    NotificationModel.CONNECTION_REQUEST,
    NotificationModel.CONNECTION_ACCEPTED,
    NotificationModel.CONNECTION_CONFIRMED,
    NotificationModel.COMMUNITY_MEMBERSHIP_REQUEST,
    NotificationModel.COMMUNITY_MEMBERSHIP_APPROVED,
    NotificationModel.COMMUNITY_MEMBERSHIP_REVOKED,
    NotificationModel.COMMUNITY_ADMIN_PRIVILEGES_GRANTED,
    NotificationModel.COMMUNITY_ADMIN_PRIVILEGES_REVOKED,
    NotificationModel.COMMUNITY_NEW_POST,
    NotificationModel.COMMUNITY_INVITE,
    NotificationModel.COMMUNITY_INVITE_DECLINED,
    NotificationModel.POST_COMMENT_USER_MENTION,
    NotificationModel.RELEASE_INFO,
]


@strawberry.type
class Query:
    @strawberry_django.field()
    def notifications(self, info, offset: int = 0, limit: int = 10) -> Paged[Notification]:
        current_user = info.context.request.user
        if current_user.is_anonymous:
            return Paged()
        return Paged.of(
            NotificationModel.objects.filter(
                owner=current_user,
                notification_type__in=PUBLISHED_NOTIFICATION_TYPES,
            ).order_by("-created"),
            offset,
            limit,
        )

    @strawberry_django.field()
    def has_new_notifications(self, info) -> NewNotificationsResponse:
        current_user = info.context.request.user
        if current_user.is_anonymous:
            return NewNotificationsResponse(id=None, status=False)

        notifications = NotificationModel.objects.filter(
            owner=current_user, notification_type__in=PUBLISHED_NOTIFICATION_TYPES
        )
        if current_user.last_seen_notification_timestamp:
            notifications = notifications.filter(created__gt=current_user.last_seen_notification_timestamp)

        return NewNotificationsResponse(id=current_user.username, status=notifications.exists())
