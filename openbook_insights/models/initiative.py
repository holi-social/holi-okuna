from django.db import models

from openbook_common.models import ModelWithUUID, LinkPreview
from openbook_common.validators import url_safety_validator
from openbook_insights.models import Insight, ExternalContentCategory


class Initiative(ModelWithUUID):
    insight = models.ForeignKey(Insight, on_delete=models.CASCADE)

    category = models.CharField(max_length=255, choices=ExternalContentCategory.choices)

    link = models.URLField(null=False, blank=False, validators=[url_safety_validator])
    link_preview = models.ForeignKey(LinkPreview, null=True, blank=True, on_delete=models.PROTECT)

    def save(self, *args, **kwargs):
        if not self.link_preview:
            self.link_preview = LinkPreview.from_url(self.link)

        if self.link != self.link_preview.requested_url:
            self.link_preview.delete()
            self.link_preview = LinkPreview.from_url(self.link)

        super().save(*args, **kwargs)
