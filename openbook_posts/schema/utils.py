from graphql import GraphQLError

from openbook_auth.models import UserBlock as UserBlockModel
from openbook.graphql_errors import GraphQLErrorCodes
from openbook_posts.models import Post as PostModel


def resolve_post(current_user, post_id):
    try:
        return (
            PostModel.objects.filter(PostModel.is_visible_query(current_user))
            .filter(UserBlockModel.not_blocked_query(current_user, "creator"))
            .get(id=post_id)
        )
    except PostModel.DoesNotExist:
        raise GraphQLError("Post not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})
