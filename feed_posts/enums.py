import strawberry
from django.db.models import TextChoices


@strawberry.enum
class VisibilityLevel(TextChoices):
    PUBLIC = ("PUBLIC",)
    REGISTERED_USERS_ONLY = ("REGISTERED_USERS_ONLY",)
