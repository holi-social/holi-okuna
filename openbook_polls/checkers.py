from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from openbook_common.utils.model_loaders import get_poll_model


def check_can_be_updated(poll, text=None):
    if poll.is_text_only_poll() and not text:
        raise ValidationError(_("Cannot remove the text of a text only poll. Try deleting it instead."))


def check_is_draft(poll):
    if not poll.is_draft():
        raise ValidationError(_("Poll is not a draft"))


def check_is_not_published(poll):
    Poll = get_poll_model()
    if poll.status == Poll.STATUS_PUBLISHED:
        raise ValidationError(_("The poll is already published"))


def check_is_not_empty(poll):
    if poll.is_empty():
        raise ValidationError(_("The poll is empty. Try adding text."))


def check_can_be_published(poll):
    check_is_draft(poll=poll)
    check_is_not_empty(poll=poll)
