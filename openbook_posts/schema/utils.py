from graphql import GraphQLError

from openbook_auth.models import UserBlock as UserBlockModel
from openbook.graphql_errors import GraphQLErrorCodes
from openbook_posts.models import Post as PostModel


def resolve_post(current_user, post_id):
    try:
        post: PostModel = PostModel.objects.filter(PostModel.is_visible_query(current_user)).get(id=post_id)
        return UserBlockModel.filter_single_object(
            current_user,
            post,
            lambda post: (temp := post.creator.id) if post and post.creator is not None else None,
        )
    except PostModel.DoesNotExist:
        raise GraphQLError("Post not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})
