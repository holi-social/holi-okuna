import re

from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError, NotFound

from openbook_terms.models import SDG

from openbook_common.utils.model_loaders import (
    get_collaboration_tool_model,
    get_community_model,
    get_external_link_model,
    get_task_model,
)


def community_name_characters_validator(community_name):
    if not re.match("^[a-zA-Z0-9_]*$", community_name):
        raise ValidationError(
            _("Community_names can only contain alphanumeric characters, underscores and dashes."),
        )


def community_name_not_taken_validator(community_name):
    Community = get_community_model()
    if Community.is_name_taken(community_name):
        raise ValidationError(
            _("Community name already taken."),
        )


def community_name_exists(community_name):
    Community = get_community_model()
    if not Community.community_with_name_exists(community_name=community_name):
        raise NotFound(
            _("No community with the provided name exists."),
        )


def sdg_with_id_exists(sdg_uuid):
    if not SDG.objects.filter(id=sdg_uuid).exists():
        raise NotFound(_(f"No sdg with the id '{sdg_uuid}' found."))


def community_id_exists(community_id):
    Community = get_community_model()
    if not Community.community_with_id_exists(community_id=community_id):
        raise NotFound(
            _("No community with the provided id exists."),
        )


def task_id_exists(task_id):
    Task = get_task_model()
    if not Task.objects.filter(id=task_id).exists():
        raise NotFound(
            _("No task with the provided id exists."),
        )


def collaboration_tool_id_exists(collaboration_tool_id):
    collaboration_tool = get_collaboration_tool_model()
    if not collaboration_tool.objects.filter(id=collaboration_tool_id).exists():
        raise NotFound(
            _("No collaboration tool with the provided id exists."),
        )


def external_link_id_exists(external_link_id):
    external_link = get_external_link_model()
    if not external_link.objects.filter(id=external_link_id).exists():
        raise NotFound(
            _("No external link with the provided id exists."),
        )
