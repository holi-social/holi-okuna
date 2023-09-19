import logging
import uuid
from typing import Optional

import strawberry
import strawberry_django

from openbook_auth.schema.types import User
from openbook_communities.schema.types import Space
from openbook_notifications.enums import NotificationType
from openbook_notifications.models import Notification as NotificationModel
from openbook_posts.schema.types import Post, PostComment

logger = logging.getLogger(__name__)


@strawberry.type
class NewNotificationsResponse:
    id: Optional[uuid.UUID]
    status: bool


@strawberry.type
class NotificationOptions:
    user: Optional[User]
    post: Optional[Post]
    post_comment: Optional[PostComment]
    space: Optional[Space]
    teaser: Optional[str]
    message: Optional[str]


@strawberry_django.type(NotificationModel)
class Notification:
    id: strawberry.auto
    owner: User
    created: strawberry.auto
    read: strawberry.auto
    notification_type: NotificationType

    @strawberry_django.field()
    def options(self) -> Optional[NotificationOptions]:
        options = self.get_options()
        return NotificationOptions(
            user=options.get("user"),
            post=options.get("post"),
            post_comment=options.get("post_comment"),
            space=options.get("space"),
            teaser=options.get("teaser"),
            message=options.get("message"),
        )
