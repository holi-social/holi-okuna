from openbook_auth.models import UserBlock as UserBlockModel
from openbook_posts.models import Post as PostModel
from django.core.exceptions import PermissionDenied


def resolve_post(current_user, post_id):
    # Check if post exists and user is not blocked => return 404 otherwise
    post: PostModel = PostModel.objects.filter(PostModel.does_exist_query()).get(id=post_id)
    UserBlockModel.filter_single_object(
        current_user,
        post,
        lambda p: None if p.creator is None else p.creator.id,
    )
    try:
        # Check if post is visible => return 403 otherwise
        return PostModel.objects.filter(PostModel.is_visible_query(current_user)).get(id=post_id)
    except PostModel.DoesNotExist:
        raise PermissionDenied()
