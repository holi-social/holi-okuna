from django.db.models import (
    CASCADE,
    ForeignKey,
    TextField,
)

from openbook_common.models import ModelWithUUID
from openbook_insights.models.insight import Insight


class Discussion(ModelWithUUID):
    insight = ForeignKey(Insight, on_delete=CASCADE, related_name="discussions")
    question = TextField(null=False, blank=False, verbose_name="Question or point for discussion")
