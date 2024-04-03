import uuid

import strawberry
import strawberry_django
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
        commentable = CommentModel.get_commentable(self.id, self.type)
        commenters = (
            UserModel.objects.select_related("profile")
            .filter(UserModel.is_visible_ignore_blocked_query())
            .filter(Q(comments__post=commentable) & CommentModel.is_visible_query(current_user, "comments"))
            .distinct()
        )
        return UserBlockModel.paged(current_user, lambda user: user.id, commenters, offset, limit)
