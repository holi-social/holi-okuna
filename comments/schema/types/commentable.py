import uuid
from typing import Optional

import strawberry
import strawberry_django

from comments.models import Comment as CommentModel
from comments.schema.types.comment import Comment
from comments.types import CommentableType
from openbook_auth.models import UserBlock as UserBlockModel
from openbook_auth.schema.types import User
from openbook_common.schema.types import Paged


@strawberry.type
class Commentable:
    id: uuid.UUID
    type: CommentableType

    @strawberry_django.field()
    def comments(
        self, info, parent_comment_id: Optional[uuid.UUID] = None, offset: int = 0, limit: int = 10
    ) -> Paged[Comment]:
        current_user = info.context.request.user

        comments = CommentModel.objects.filter(
            commentable_id=self.id,
            commentable_type__model=self.type.value,
            is_deleted=False,
            parent_comment_id=parent_comment_id,
        ).order_by("created")

        return UserBlockModel.paged(current_user, lambda comment: comment.commenter.id, comments, offset, limit)

    @strawberry_django.field()
    def commenters(self, info, offset: int = 0, limit: int = 10) -> Paged[User]:
        current_user = info.context.request.user

        commenters = CommentModel.get_commenters(commentable_id=self.id, commentable_type=self.type, user=current_user)

        return UserBlockModel.paged(current_user, lambda user: user.id, commenters, offset, limit)

    @strawberry_django.field()
    def top_comment(self, info) -> Optional[Comment]:
        current_user = info.context.request.user
        return CommentModel.get_top_comment(self.id, self.type, current_user)

    @strawberry_django.field()
    def total_comments(self) -> int:
        return CommentModel.total_comments(commentable_id=self.id, commentable_type=self.type)
