from django.db.models import (
    URLField,
    TextField,
    CASCADE,
    CharField,
    ForeignKey,
    SET_NULL,
)

from openbook_common.models import ModelWithUUID, LinkPreview
from openbook_common.validators import url_safety_validator
from openbook_insights.models.external_content import ExternalContentCategory
from openbook_insights.models.insight import Insight


class Recommendation(ModelWithUUID):
    insight = ForeignKey(Insight, on_delete=CASCADE, related_name="recommendations")

    category = CharField(choices=ExternalContentCategory.choices, max_length=255, null=False, blank=False)
    link = URLField(null=False, blank=False, validators=[url_safety_validator])
    link_preview = ForeignKey(LinkPreview, on_delete=SET_NULL, null=True)
    comment = TextField(null=False, blank=False, verbose_name="Why I recommend this content")

    def save(self, *args, **kwargs):
        if not self.link_preview:
            self.link_preview = LinkPreview.from_url(self.link)

        if self.link != self.link_preview.requested_url:
            self.link_preview.delete()
            self.link_preview = LinkPreview.from_url(self.link)

        super().save(*args, **kwargs)
