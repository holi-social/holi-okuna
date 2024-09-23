import strawberry
from django.db.models import TextChoices


@strawberry.enum
class VisibilityLevel(TextChoices):
    PUBLIC = ("PUBLIC",)
    REGISTERED_USERS_ONLY = ("REGISTERED_USERS_ONLY",)


@strawberry.enum
class AspectRatio(TextChoices):
    SIXTEEN_NINE = ("SIXTEEN_NINE",)
    ONE_ONE = ("ONE_ONE",)
