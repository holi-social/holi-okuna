from enum import Enum

import strawberry
from django.db.models import TextChoices


@strawberry.enum
class ReactionType(TextChoices):
    HEART = ("HEART",)


@strawberry.enum
class ReactionAction(Enum):
    SET = "SET"
    REMOVE = "REMOVE"


@strawberry.enum
class VisibilityType(TextChoices):
    MEMBERS = ("MEMBERS",)
    PUBLIC = ("PUBLIC",)


@strawberry.enum
class NeedUpdateType(TextChoices):
    NO = ("NO",)
    RECOMMENDED = ("RECOMMENDED",)
    MANDATORY = ("MANDATORY",)
