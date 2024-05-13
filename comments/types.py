from enum import Enum

import strawberry


@strawberry.enum
class CommentableType(Enum):
    POST = "post"
    DISCUSSION = "discussion"
    FEED_POST = "feedpost"
