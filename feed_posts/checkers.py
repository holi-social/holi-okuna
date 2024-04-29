from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from feed_posts.enums import VisibilityLevel


class FeedPostChecker:
    def check_can_query_registered_users_only_feed_posts(self, user, post):
        if post.visibility == VisibilityLevel.REGISTERED_USERS_ONLY and user.is_anonymous:
            raise ValidationError(_("You cannot query registered only users feed posts"))
