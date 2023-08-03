from typing import Optional

from openbook.graphql_types import Post
from openbook_auth.models import User
from openbook_communities.models import Community
from openbook_notifications.models import Notification


class TestAssertionsMixin:
    def assertNotification(
        self,
        notification: Notification,
        type: Optional[str] = None,
        user: Optional[User] = None,
        space: Optional[Community] = None,
        post: Optional[Post] = None,
    ):
        assert notification.notification_type == type
        options = notification.get_options()
        if user:
            assert options["user"] == user
        if space:
            assert options["space"] == space
        if post:
            assert options["post"] == post
