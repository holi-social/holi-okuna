import pytest
from django.shortcuts import reverse
from django.test import TransactionTestCase

from openbook_auth.models import User
from openbook_common.tests.assertions import TestAssertionsMixin
from openbook_common.tests.helpers import make_post, make_users
from openbook_notifications.models import Notification
from openbook_notifications.models.release_notification import ReleaseNotification


class MyAdminTestCase(TestAssertionsMixin, TransactionTestCase):
    fixtures = [
        "openbook_common/fixtures/languages.json",
    ]

    def setUp(self) -> None:
        self.username = "superuser"
        self.password = "123"  # noqa: S105
        self.superuser = User.objects.create_superuser(
            username=self.username, email="foo@bar.de", password=self.password, is_staff=True
        )
        self.client.login(username=self.username, password=self.password)

    def tearDown(self) -> None:
        self.superuser.delete()

    @pytest.mark.skip
    def test_release_notification_send(self):
        users = make_users(3)

        unsent_notification = ReleaseNotification.objects.create(post=make_post(user=users[0]))
        already_sent_notification = ReleaseNotification.objects.create(post=make_post(user=users[0]), is_sent=True)

        response = self.client.post(
            reverse("admin:openbook_notifications_releasenotification_changelist"),
            data={
                "action": "send",
                "_selected_action": [
                    unsent_notification.id,
                    already_sent_notification.id,
                ],
            },
            follow=True,
        )

        admin_messages = list(response.context["messages"])
        unsent_notification_admin_message = next(
            x for x in admin_messages if unsent_notification.post.title in x.message
        )
        sent_notification_admin_message = next(
            x for x in admin_messages if already_sent_notification.post.title in x.message
        )

        users_including_superuser = len(users) + 1
        self.assertEqual(unsent_notification_admin_message.level_tag, "info")
        self.assertIn(f"sent to {users_including_superuser} Users", unsent_notification_admin_message.message)

        self.assertEqual(sent_notification_admin_message.level_tag, "warning")
        self.assertIn("already been sent", sent_notification_admin_message.message)

        for user in users:
            self.assertEqual(len(user.notifications.all()), 1)
            self.assert_notification(
                user.notifications.get(), type=Notification.RELEASE_INFO, post=unsent_notification.post
            )
