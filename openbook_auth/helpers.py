from openbook_common.helpers import create_upload_filename


def upload_to_user_avatar_directory(user_profile, filename):
    return create_upload_filename(
        username=user_profile.user.username,
        object_type="avatar",
        object_id=user_profile.user.username,
        filename=filename,
    )


def upload_to_user_cover_directory(user_profile, filename):
    return create_upload_filename(
        username=user_profile.user.username,
        object_type="user_cover",
        object_id=user_profile.user.username,
        filename=filename,
    )
