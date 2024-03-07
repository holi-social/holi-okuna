from enum import auto

from django.db.models import TextChoices


class ExternalContentCategory(TextChoices):
    ARTICLE = auto()
    VIDEO = auto()
    AUDIO = auto()
    SOCIAL_MEDIA = auto()
    POST = auto()
    STUDY = auto()
    DONATION_PROJECT = auto()
    VOLUNTEERING = auto()
    TIP = auto()
    SPACE = auto()
    EVENT = auto()
