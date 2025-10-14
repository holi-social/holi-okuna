import re

from graphql import GraphQLError
from rest_framework.exceptions import ValidationError, NotFound
from django.utils.translation import gettext_lazy as _

from openbook.graphql_errors import GraphQLErrorCodes
from openbook_common.enums import ReactionType
from openbook_common.helpers import extract_urls_from_string
from openbook_common.utils.model_loaders import (
    get_emoji_model,
    get_emoji_group_model,
    get_language_model,
)
from openbook_common.topics import topic_v2_slugs
from openbook_common.skills import skill_v2_slugs

from openbook import settings

# TODO performance this import takes quite some time
from google.cloud.webrisk_v1 import WebRiskServiceClient, SearchUrisRequest, ThreatType
import structlog

logger = structlog.getLogger(__name__)

ENVIRONMENT_ID = settings.ENVIRONMENT_ID


def is_valid_hex_color(hex_color):
    return re.search(r"^#(?:[0-9a-fA-F]{3}){1,2}$", hex_color)


def hex_color_validator(hex_color):
    if not is_valid_hex_color(hex_color):
        raise ValidationError(
            _("The provided value is not a valid hex color."),
        )


def emoji_id_exists(list_id):
    Emoji = get_emoji_model()
    if not Emoji.objects.filter(pk=list_id).exists():
        raise ValidationError(
            _("No emoji with the provided id exists."),
        )


def reaction_type_exists(reaction_type):
    try:
        ReactionType[reaction_type]
    except KeyError:
        raise ValidationError(
            _("No reaction_type with the provided name exists."),
        ) from None


def emoji_group_id_exists(emoji_group_id):
    EmojiGroup = get_emoji_group_model()
    if not EmojiGroup.objects.filter(pk=emoji_group_id).exists():
        raise ValidationError(
            _("No emoji group with the provided id exists."),
        )


def name_characters_validator(name):
    if ">" in name or "<" in name:
        raise ValidationError(
            _("Names can't contain < or >."),
        )


def language_id_exists(language_id):
    Language = get_language_model()
    if not Language.objects.filter(pk=language_id).exists():
        raise ValidationError(
            _("No supported language with the provided id exists."),
        )


def language_code_exists(language_code):
    Language = get_language_model()
    if not Language.objects.filter(code=language_code).exists():
        raise ValidationError(
            _("No supported language with the provided code exists."),
        )


def url_safety_validator(url: str):
    if ENVIRONMENT_ID == "local":
        return

    webrisk_client = WebRiskServiceClient()

    request = SearchUrisRequest()
    request.uri = url
    request.threat_types = [
        ThreatType.MALWARE,
        ThreatType.SOCIAL_ENGINEERING,
        ThreatType.SOCIAL_ENGINEERING_EXTENDED_COVERAGE,
        ThreatType.UNWANTED_SOFTWARE,
    ]

    response = webrisk_client.search_uris(request)
    threat_types = response.threat.threat_types

    if threat_types:
        logger.debug(f"The link has the following threat types: {threat_types}")
        raise GraphQLError(
            _("Unsafe link detected, please check."), extensions={"code": GraphQLErrorCodes.MALICIOUS_URL}
        )


def string_not_empty(string):
    if not re.match("\\S", string):
        raise ValidationError("You must provide at least one character in the search string")


def sanitize_text(text: str):
    urls = extract_urls_from_string(text)
    for url in urls:
        url_safety_validator(url)


def topic_v2_exists(topic_v2_slug):
    if topic_v2_slug not in topic_v2_slugs:
        raise NotFound(_(f"TopicV2 '{topic_v2_slug}' does not exist."))


def skill_v2_exists(skill_v2_slug):
    if skill_v2_slug not in skill_v2_slugs:
        raise NotFound(_(f"SkillV2 '{skill_v2_slug}' does not exist."))
