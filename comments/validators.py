from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from openbook_common.utils.helpers import extract_hashtags_from_string


def comment_text_hashtags_validator(post_text):
    hashtags = extract_hashtags_from_string(post_text)
    if len(hashtags) > settings.POST_COMMENT_MAX_HASHTAGS:
        raise ValidationError(
            _("Please add a maximum of %(max_hashtags)d hashtags.")
            % {
                "max_hashtags": settings.POST_MAX_HASHTAGS,
            }
        )

    for hashtag in hashtags:
        if len(hashtag) > settings.HASHTAG_NAME_MAX_LENGTH:
            raise ValidationError(
                _("Please keep hashtags under %(max_characters)d characters.")
                % {
                    "max_characters": settings.HASHTAG_NAME_MAX_LENGTH,
                }
            )


comment_text_validators = [comment_text_hashtags_validator]
