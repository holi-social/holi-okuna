from enum import Enum

import strawberry


@strawberry.enum
class ContentType(str, Enum):
    POST = "POST"
    POST_COMMENT = "POST_COMMENT"
    USER = "USER"
    SPACE = "SPACE"
    SPACE_TASK = "SPACE_TASK"
    FEED_POST = "FEED_POST"
    SPACE_APPOINTMENT = "SPACE_APPOINTMENT"
