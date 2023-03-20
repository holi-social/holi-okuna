from django.shortcuts import reverse
from django.shortcuts import reverse
from django.test import TestCase

from openbook_auth.models import User
from openbook_common.tests.assertions import TestAssertionsMixin
from openbook_common.tests.helpers import make_post, make_users
from openbook_notifications.models import Notification
from openbook_notifications.models.release_notification import ReleaseNotification


class MyAdminTestCase(TestAssertionsMixin, TestCase):
    fixtures = [
        "openbook_circles/fixtures/circles.json",
        "openbook_common/fixtures/languages.json",
    ]

    def setUp(self) -> None:
        self.username = "superuser"
        self.password = "123"
        self.superuser = User.objects.create_superuser(
            username=self.username, email="foo@bar.de", password=self.password, is_staff=True
        )
        self.client.login(username=self.username, password=self.password)

    def test_admin_action(self):
        users = make_users(3)

        post = make_post()
        release_notification = ReleaseNotification.objects.create(post=post)
        already_sent_notification = ReleaseNotification.objects.create(post=post, is_sent=True)

        response = self.client.post(
            reverse("admin:openbook_notifications_releasenotification_changelist"),
            data={
                "action": "send",
                "_selected_action": [
                    str(release_notification.id),
                    str(already_sent_notification.id),
                ],
            },
            follow=True,
        )

        # response.context["messages"] could be used to test messages

        for user in users:
            self.assertNotification(user.notifications.get(), type=Notification.RELEASE, post=post)
