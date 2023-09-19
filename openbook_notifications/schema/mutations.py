import uuid

import strawberry
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache

from openbook_auth.utils import verify_authorized_user
from openbook_notifications.schema.types import NewNotificationsResponse


@strawberry.type
class Mutation:
    @strawberry.mutation
    @sync_to_async
    def last_seen_notification(self, info, notification_id: uuid.UUID) -> NewNotificationsResponse:
        current_user = verify_authorized_user(info)
        current_user.store_last_seen_notification(notification_id)

        # Update user cache in order to update the value of last_seen_notification_timestamp
        cache.set(f"{settings.USER_CACHE_PREFIX}{current_user.username}", current_user, timeout=300)

        return NewNotificationsResponse(id=current_user.username, status=False)
