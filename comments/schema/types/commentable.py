import uuid
from typing import Optional

import strawberry
import strawberry_django
from django.db.models import Q

from comments.models.commentable import CommentableType
from comments.models import Comment as CommentModel
from comments.schema.types.comment import Comment
from openbook_auth.models import User as UserModel
from openbook_auth.models import UserBlock as UserBlockModel
from openbook_auth.schema.types import User
from openbook_common.schema.types import Paged


@strawberry.type
class Commentable:
    id: uuid.UUID
    type: CommentableType

    @strawberry_django.field()
    def comments(self, info, offset: int = 0, limit: int = 10) -> Paged[Comment]:
        current_user = info.context.request.user
        comments = (
            CommentModel.objects.filter(commentable_id=self.id, commentable_type__model=self.type.value)
            .filter(is_deleted=False)
            .order_by("created")
        )
        return UserBlockModel.paged(current_user, lambda comment: comment.commenter.id, comments, offset, limit)

    @strawberry_django.field()
    def commenters(self, info, offset: int = 0, limit: int = 10) -> Paged[User]:
        current_user = info.context.request.user

        commenters = (
            UserModel.objects.select_related("profile")
            .filter(UserModel.is_visible_ignore_blocked_query())
            .filter(
                Q(comments__commentable_id=self.id, comments__commentable_type__model=self.type.value)
                & CommentModel.is_visible_query(current_user, "comments")
            )
            .distinct()
        )

        return UserBlockModel.paged(current_user, lambda user: user.id, commenters, offset, limit)

    @strawberry_django.field()
    def top_comment(self, info) -> Optional[Comment]:
        current_user = info.context.request.user
        return CommentModel.get_top_comment(self.id, self.type, current_user)
