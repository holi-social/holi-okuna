from enum import Enum

import strawberry


@strawberry.enum
class ContentType(Enum):
    POST = "POST"
    POST_COMMENT = "POST_COMMENT"
    USER = "USER"
    SPACE = "SPACE"
