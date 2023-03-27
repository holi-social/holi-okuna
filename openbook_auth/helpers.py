from graphql import GraphQLError

from openbook.graphql_errors import GraphQLErrorCodes
from openbook_auth import models as auth_models
from openbook_common import helpers as common_helpers


def upload_to_user_avatar_directory(user_profile, filename):
    return common_helpers.create_upload_filename(
        username=user_profile.user.username,
        object_type="avatar",
        object_id=user_profile.user.username,
        filename=filename,
    )


def upload_to_user_cover_directory(user_profile, filename):
    return common_helpers.create_upload_filename(
        username=user_profile.user.username,
        object_type="user_cover",
        object_id=user_profile.user.username,
        filename=filename,
    )


def verify_authorized_user(info):
    current_user: auth_models.User = info.context.request.user
    if not current_user or current_user.is_anonymous:
        raise GraphQLError("Unauthorized", extensions={"code": GraphQLErrorCodes.UNAUTHORIZED})
    return current_user
