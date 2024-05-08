from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from feed_posts.enums import VisibilityLevel


class FeedPostChecker:
    def check_can_query_registered_users_only_feed_posts(self, user, post):
        if post.visibility == VisibilityLevel.REGISTERED_USERS_ONLY and user.is_anonymous:
            raise ValidationError(_("You cannot query registered only users feed posts"))

    def check_can_update_feed_post(self, user, post):
        if post.creator != user:
            raise ValidationError(_("You cannot update this feed post"))

    def check_can_delete_feed_post(self, user, post):
        if post.creator != user:
            raise ValidationError(_("You cannot delete this feed post"))
