from enum import Enum


class CommentableType(Enum):
    class Meta:
        abstract = True

    POST = "post"
    DISCUSSION = "discussion"
