from django.db import models
from django.utils.translation import gettext_lazy as _
from openbook import settings
from openbook_common.models import ModelWithUUID


class Term(ModelWithUUID):
    class Meta:
        abstract = True

    title = models.CharField(_("title"), max_length=settings.TERM_TITLE_MAX_LENGTH, blank=False)
    slug = models.SlugField(_("slug"), max_length=settings.TERM_SLUG_MAX_LENGTH, unique=True)

    def __str__(self):
        return f"{self.__class__.__name__}: {self.title} ({self.id})"


# Create your models here.
class Topic(Term):
    """
    A topic is something that a user can be interested in and that categorizes
    Insights, Posts and Spaces.
    """

    is_discover_spaces_default = models.BooleanField(_("is discover spaces default"), default=False)
    """
    Indicates if the topic is included in the list of default topics suggested
    on the 'Discover spaces' page.
    """


class SDG(Term):
    """
    SDG == Sustainable Development Goals. The 17 goals defined by the UN.
    see: https://sdgs.un.org/
    """

    number = models.IntegerField(_("number"), null=False, blank=False, default=False)


class Skill(Term):
    """
    A skill is something that a user is capable of and that a task can request.
    """
