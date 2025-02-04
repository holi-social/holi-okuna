import typing

from django.conf import settings
from django.db.models import Q, QuerySet
from django.template.defaultfilters import slugify

from openbook_auth.models import UserRole
from openbook_common.helpers import create_upload_filename
from openbook_common.utils.model_loaders import get_community_membership_model
from openbook_communities.validators import community_name_not_taken_validator
from rest_framework.exceptions import ValidationError

if typing.TYPE_CHECKING:
    from openbook_communities.models import Community


def upload_to_community_avatar_directory(community, filename):
    return create_upload_filename(
        username=community.creator.username,
        object_type="community",
        object_id=community.id,
        filename=filename,
    )


def upload_to_community_cover_directory(community, filename):
    return create_upload_filename(
        username=community.creator.username,
        object_type="community_cover",
        object_id=community.id,
        filename=filename,
    )


def upload_to_community_tool_thumbnail_directory(tool, filename):
    return create_upload_filename(
        username=tool.community.creator.username,
        object_type="community_tool_thumbnail",
        object_id=tool.id,
        filename=filename,
    )


def upload_to_community_task_thumbnail_directory(task, filename):
    return create_upload_filename(
        username=task.community.creator.username,
        object_type="community_task_thumbnail",
        object_id=task.id,
        filename=filename,
    )


def create_community_name_from_title_and_hash(title, hash):
    slug = slugify(title)
    name = slug
    try:
        community_name_not_taken_validator(name)
        return name
    except ValidationError:
        name_suffix_length = min(8, len(hash))
        while name_suffix_length <= len(hash) and name_suffix_length > 0:
            name = (
                f"{slug[: settings.COMMUNITY_NAME_MAX_LENGTH - name_suffix_length - 1]}-{hash[: name_suffix_length]}"
            )
            try:
                community_name_not_taken_validator(name)
                return name
            except ValidationError:
                name_suffix_length = name_suffix_length + 1
        raise


def get_space_representatives(space: "Community") -> QuerySet:
    CommunityMembership = get_community_membership_model()

    any_admin = CommunityMembership.objects.filter(Q(community=space) & Q(is_administrator=True))
    without_employees = any_admin.exclude(Q(user__is_employee=True) | Q(user__role=UserRole.INTERNAL))

    if without_employees.count() > 0:
        return without_employees

    return any_admin
