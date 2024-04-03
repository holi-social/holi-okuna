import logging
import uuid

import strawberry
import strawberry_django
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from comments.enums import CommentableType
from comments.models import Comment as CommentModel
from openbook_auth.models import User as UserModel
from openbook_auth.models import UserBlock as UserBlockModel
from openbook_auth.schema.types import User
from openbook_common.schema.types import Paged


@strawberry.type
class Commentable:
    id: uuid.UUID
    type: CommentableType

    @strawberry_django.field()
    def commenters(self, info, offset: int = 0, limit: int = 10) -> Paged[User]:
        current_user = info.context.request.user
        commentable_content_type = ContentType.objects.get(model=self.type.value)

        commenters = (
            UserModel.objects.select_related("profile")
            .filter(UserModel.is_visible_ignore_blocked_query())
            .filter(
                Q(comments__commentable_id=self.id, comments__commentable_type=commentable_content_type)
                & CommentModel.is_visible_query(current_user, "comments")
            )
            .order_by("-comments__created")
            .distinct()
        )

        return UserBlockModel.paged(current_user, lambda user: user.id, commenters, offset, limit)
