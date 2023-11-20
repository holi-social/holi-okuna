from graphql import GraphQLError

from openbook_auth.models import UserBlock as UserBlockModel
from openbook.graphql_errors import GraphQLErrorCodes
from openbook_posts.models import Post as PostModel


def resolve_post(current_user, post_id):
    try:
        post: PostModel = PostModel.objects.filter(PostModel.is_visible_query(current_user)).get(id=post_id)
        # don't return post if creator is blocked, answer from cache instead of in query
        if post.creator.id in UserBlockModel.users_blocking_or_blocked(current_user):
            raise PostModel.DoesNotExist()
        post.comments

        return post
    except PostModel.DoesNotExist:
        raise GraphQLError("Post not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})
