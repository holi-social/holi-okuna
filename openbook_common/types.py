from enum import Enum

from django.utils.translation import gettext_lazy as _
from django.db.models import TextChoices
from strawberry_django_plus import gql


@gql.enum
class ReactionType(str, Enum):
    HEART = "HEART"


@gql.enum
class VisibilityType(TextChoices):
    MEMBERS = ("MEMBERS",)
    PUBLIC = ("PUBLIC",)
