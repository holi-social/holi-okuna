import uuid

import strawberry
import strawberry_django
from django.core.exceptions import PermissionDenied

from comments.enums import CommentableType
from comments.models import Comment as CommentModel
from comments.schema.types.commentable import Commentable


@strawberry.type
class Query:
    @strawberry_django.field()
    def commentable(self, info, id: uuid.UUID, type: CommentableType) -> Commentable:
        commentable = CommentModel.get_commentable(id, type)

        if not commentable.can_be_viewed(info.context.request.user):
            raise PermissionDenied()

        return Commentable(id=id, type=type)
