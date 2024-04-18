import uuid

from django.db.models import (
    CASCADE,
    ForeignKey,
    TextField,
)
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import (
    ValidationError,
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

    def delete_comment(self, commenter: User, id: uuid.UUID):
        comment = Comment.objects.get(pk=id)
        is_comment_creator = comment.commenter_id == commenter.id

        if is_comment_creator:
            comment.delete()
        else:
            raise ValidationError(_("You cannot remove a comment that does not belong to you"))

    def can_view(user: User) -> bool:
        return True
