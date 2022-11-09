from django.db import models
from django.utils.translation import gettext_lazy as _
from openbook import settings
from openbook_common.models import ModelWithUUID


# Create your models here.
class Topic(ModelWithUUID):
    """
    A topic is something that a user can be interested in and that categorizes
    Insights, Posts and Spaces
    """

    title = models.CharField(
        _("title"), max_length=settings.TOPIC_TITLE_MAX_LENGTH, blank=False
    )


class SDG(ModelWithUUID):
    """
    SDG == Sustainable Development Goals. The 17 goals defined by the UN.
    see: https://sdgs.un.org/
    """

    title = models.CharField(
        _("title"), max_length=settings.SDG_TITLE_MAX_LENGTH, blank=False
    )


class Skill(ModelWithUUID):
    """
    A skill is something that a user is capable of and that a task can request.
    """

    title = models.CharField(
        _("title"), max_length=settings.SKILL_TITLE_MAX_LENGTH, blank=False
    )
