from typing import Optional
from unittest import TestCase

from openbook.graphql_types import Post
from openbook_auth.models import User
from openbook_communities.models import Community
from openbook_notifications.models import Notification


class TestAssertionsMixin(TestCase):
    def assertNotification(
        self,
        notification: Notification,
        type: Optional[str] = None,
        user: Optional[User] = None,
        space: Optional[Community] = None,
        post: Optional[Post] = None,
    ):
        self.assertEquals(notification.notification_type, type)
        options = notification.get_options()
        if user:
            self.assertEquals(options["user"], user)
        if space:
            self.assertEquals(options["space"], space)
        if post:
            self.assertEquals(options["post"], post)
