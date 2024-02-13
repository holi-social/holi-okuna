from graphql import GraphQLError

from openbook_auth.models import UserBlock as UserBlockModel
from openbook.graphql_errors import GraphQLErrorCodes
from openbook_posts.models import Post as PostModel


def resolve_post(current_user, post_id):
    try:
        # Check if post exists and user is not blocked => return 404 otherwise
        post: PostModel = PostModel.objects.filter(PostModel.does_exist_query()).distinct().get(id=post_id)
        UserBlockModel.filter_single_object(
            current_user,
            post,
            lambda p: None if p.creator is None else p.creator.id,
        )
        try:
            # Check if post is visible => return 403 otherwise
            return PostModel.objects.filter(PostModel.is_visible_query(current_user)).distinct().get(id=post_id)
        except PostModel.DoesNotExist:
            raise GraphQLError("Unauthorized", extensions={"code": GraphQLErrorCodes.UNAUTHORIZED})
    except PostModel.DoesNotExist:
        raise GraphQLError("Post not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})
