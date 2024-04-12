from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from openbook_common.utils.model_loaders import get_question_model


def check_can_be_updated(question, text=None):
    if question.is_text_only_question() and not text:
        raise ValidationError(_("Cannot remove the text of a text only question. Try deleting it instead."))


def check_is_draft(question):
    if not question.is_draft():
        raise ValidationError(_("Question is not a draft"))
    

def check_is_not_published(question):
    Question = get_question_model()
    if question.status == Question.STATUS_PUBLISHED:
        raise ValidationError(_("The question is already published"))


def check_is_not_empty(quesiton):
    if quesiton.is_empty():
        raise ValidationError(_("The question is empty. Try adding text."))


def check_can_be_published(question):
    check_is_draft(question=question)
    check_is_not_empty(quesiton=question)

