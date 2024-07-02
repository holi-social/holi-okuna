from enum import Enum

import strawberry
from django.db.models import TextChoices


@strawberry.enum
class ReactionType(TextChoices):
    HEART = ("HEART",)  # Deprecated
    LOVE = ("LOVE",)
    SUPPORT = ("SUPPORT",)
    HOPE = ("HOPE",)
    CELEBRATE = ("CELEBRATE",)
    INSIGHT = ("INSIGHT",)
    SUCCESS = ("SUCCESS",)

    # 'HEART' is deprecated, use 'LOVE' instead
    @classmethod
    def get_value(cls, value):
        if value == cls.HEART:
            return cls.LOVE
        return value


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


@strawberry.enum
class FeatureToggleType(TextChoices):
    OFF = ("OFF",)
    PREVIEW = ("PREVIEW",)
    PRODUCTION = ("PRODUCTION",)
    MAINTENANCE = ("MAINTENANCE",)


class FeatureToggleName(Enum):
    NOTIFICATIONS = "NOTIFICATIONS"
