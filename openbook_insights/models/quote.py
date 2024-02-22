from django.db import models

from openbook_common.models import ModelWithUUID, LinkPreview
from openbook_common.validators import url_safety_validator
from openbook_insights.models import Insight
from openbook_insights.models.external_content import ExternalContentCategory


class Quote(ModelWithUUID):
    insight = models.ForeignKey(Insight, on_delete=models.CASCADE, related_name="quotes")

    quote = models.TextField(blank=False, null=False)

    quote_author = models.CharField(max_length=255, blank=False, null=False)
    quote_author_profession = models.CharField(max_length=255, blank=False, null=False)

    link = models.URLField(blank=False, null=False, validators=[url_safety_validator])
    link_preview = models.ForeignKey(LinkPreview, on_delete=models.SET_NULL, null=True)
    category = models.CharField(max_length=255, choices=ExternalContentCategory.choices)

    comment = models.TextField(blank=False, null=False, verbose_name="Why I recommend this content")

    def save(self, *args, **kwargs):
        if not self.link_preview:
            self.link_preview = LinkPreview.from_url(self.link)

        if self.link != self.link_preview.requested_url:
            self.link_preview.delete()
            self.link_preview = LinkPreview.from_url(self.link)

        super().save(*args, **kwargs)
