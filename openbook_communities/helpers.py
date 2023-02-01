import re

from django.conf import settings

from openbook_common.helpers import create_upload_filename


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


def create_community_name_from_title(title):
    invalid_characters = r"[^a-zA-Z0-9_]"
    name = re.sub(r"\s", "_", (title or "").replace("-", "_"))
    return re.sub(invalid_characters, "", name).lower()[: settings.COMMUNITY_NAME_MAX_LENGTH]
