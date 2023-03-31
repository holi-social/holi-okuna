from django.conf import settings
from django.template.defaultfilters import slugify

from openbook_common.helpers import create_upload_filename
from openbook_communities.validators import community_name_not_taken_validator
from rest_framework.exceptions import ValidationError


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


def upload_to_community_task_thumbnail_directory(community, filename):
    return create_upload_filename(
        username=community.creator.username,
        object_type="community_task_thumbnail",
        object_id=community.id,
        filename=filename,
    )


def create_community_name_from_title_and_hash(title, hash):
    name = slugify(title)
    try:
        community_name_not_taken_validator(name)
        return name
    except ValidationError:
        name_suffix_length = min(8, len(hash))
        while name_suffix_length <= len(hash) and name_suffix_length > 0:
            name = (
                f"{title[: settings.COMMUNITY_NAME_MAX_LENGTH - name_suffix_length - 1]}-{hash[: name_suffix_length]}"
            )
            try:
                community_name_not_taken_validator(name)
                return name
            except ValidationError:
                name_suffix_length = name_suffix_length + 1
        raise
