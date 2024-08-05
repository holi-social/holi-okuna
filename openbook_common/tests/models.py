from unittest.mock import patch

from rest_framework.test import APITransactionTestCase


class OpenbookAPITestCase(APITransactionTestCase):
    def setUp(self):
        pass
        # self.patcher = patch("openbook_notifications.helpers._send_notification_to_user")
        # self.mock_foo = self.patcher.start()

    def tearDown(self):
        pass
        # self.patcher.stop()
