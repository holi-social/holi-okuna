import uuid

import strawberry
import strawberry_django

from comments.enums import CommentableType
from comments.schema.types.commentable import Commentable


@strawberry.type
class Query:
    @strawberry_django.field()
    def commentable(self, info, id: uuid.UUID, type: CommentableType) -> Commentable:
        return Commentable(id=id, type=type)
