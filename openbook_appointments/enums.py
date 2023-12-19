import strawberry
from django.db.models import TextChoices


@strawberry.enum
class PermissionType(TextChoices):
    PARTICIPANTS = ("PARTICIPANTS",)
    ADMINS = ("ADMINS",)


@strawberry.enum
class StatusType(TextChoices):
    PAST = ("PAST",)
    UPCOMING = ("UPCOMING",)
