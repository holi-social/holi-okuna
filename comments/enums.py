from enum import Enum

import strawberry


@strawberry.enum
class CommentableType(Enum):
    POST = "post"
