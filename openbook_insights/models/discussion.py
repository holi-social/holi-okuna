from django.db.models import (
    CASCADE,
    ForeignKey,
    TextField,
)

from comments.models import Comment
from openbook_auth.models import User
from openbook_common.models import ModelWithUUID
from openbook_insights.models.insight import Insight


class Discussion(ModelWithUUID):
    insight = ForeignKey(Insight, on_delete=CASCADE, related_name="discussions")
    question = TextField(null=False, blank=False, verbose_name="Question or talking point for discussion")

    def comment_on(self, commenter: User, text: str):
        return Comment.create_comment(text=text, commenter=commenter, commentable=self)
