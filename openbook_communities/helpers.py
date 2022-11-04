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
