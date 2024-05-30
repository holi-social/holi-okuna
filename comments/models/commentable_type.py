from enum import Enum


class EnabledCommentableType(Enum):
    class Meta:
        abstract = True

    POST = "post"
    DISCUSSION = "discussion"
    FEED_POST = "feedpost"
