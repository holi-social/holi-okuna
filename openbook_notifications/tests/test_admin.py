from django.contrib.admin.sites import AdminSite
from django.shortcuts import reverse
from django.test import RequestFactory, TestCase
from django.contrib.messages.storage.fallback import FallbackStorage


from openbook_auth.models import User
from openbook_notifications.admin import ReleaseNotificationAdmin
from openbook_notifications.models.release_notification import ReleaseNotification


class MyAdminTestCase(TestCase):
    def setUp(self) -> None:
        self.superuser = User.objects.create_superuser(username="superuser", email="foo@bar.de", is_staff=True)
        self.client.force_login(self.superuser)

    def test_admin_action(self):
        action_url = reverse("admin:openbook_notifications_releasenotification_changelist")

        request = self.client.post(action_url, data={"action": "send_notifications", "_selected"})
        self.assertTrue(False)
