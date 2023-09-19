from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import NotFound, ValidationError

from openbook_common.utils.helpers import extract_hashtags_from_string
from openbook_common.utils.model_loaders import (
    get_post_comment_model,
    get_post_comment_reaction_model,
    get_post_model,
    get_post_reaction_model,
)

SORT_CHOICES = ["ASC", "DESC"]


def post_id_exists(post_id):
    Post = get_post_model()
    if not Post.objects.filter(id=post_id).exists():
        raise ValidationError(
            _("The post does not exist."),
        )


def post_comment_id_exists(post_comment_id):
    PostComment = get_post_comment_model()

    if not PostComment.objects.filter(id=post_comment_id).exists():
        raise ValidationError(
            _("The post comment does not exist."),
        )


def post_comment_id_exists_for_post_with_id(post_comment_id, post_id):
    PostComment = get_post_comment_model()

    if not PostComment.objects.filter(id=post_comment_id, post__id=post_id).exists():
        raise ValidationError(
            _("The post comment does not exist."),
        )


def post_comment_reaction_id_exists_for_post_with_id_and_comment_with_id(
    post_comment_reaction_id, post_comment_id, post_id
):
    PostCommentReaction = get_post_comment_reaction_model()

    if not PostCommentReaction.objects.filter(
        id=post_comment_reaction_id,
        post_comment_id=post_comment_id,
        post_comment__post__id=post_id,
    ).exists():
        raise ValidationError(
            _("The post comment reaction does not exist."),
        )


def post_reaction_id_exists(post_reaction_id):
    PostReaction = get_post_reaction_model()

    if not PostReaction.objects.filter(id=post_reaction_id).exists():
        raise ValidationError(
            _("The post reaction does not exist."),
        )


def post_comment_reaction_id_exists(post_comment_reaction_id):
    PostCommentReaction = get_post_comment_reaction_model()

    if not PostCommentReaction.objects.filter(id=post_comment_reaction_id).exists():
        raise ValidationError(
            _("The post comment reaction does not exist."),
        )


def post_text_hashtags_validator(post_text):
    hashtags = extract_hashtags_from_string(post_text)
    if len(hashtags) > settings.POST_MAX_HASHTAGS:
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


post_text_validators = [post_text_hashtags_validator]


def post_comment_text_hashtags_validator(post_text):
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


post_comment_text_validators = [post_comment_text_hashtags_validator]
