import strawberry
from django.db.models import TextChoices


@strawberry.enum
class PermissionType(TextChoices):
    PARTICIPANTS = ("PARTICIPANTS",)
    ADMINS = ("ADMINS",)
