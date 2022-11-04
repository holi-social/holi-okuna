from django.db import models
from django.conf import settings
from django.utils.timezone import now

# Create your models here.
from openbook_auth.models import User
from openbook_common.models import ModelWithUUID


class Space(ModelWithUUID):
    title = models.CharField(max_length=settings.SPACE_TITLE_MAX_LENGTH, blank=False)
    description = models.TextField(blank=False)
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_spaces",
        blank=True,
        null=True,
    )
    created = models.DateTimeField(default=now, editable=False)
