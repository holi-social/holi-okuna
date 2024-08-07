from rest_framework.test import APITransactionTestCase

# ruff: noqa:ERA001

# if you ever need to e.g. set up mocking, you can prepare that here, e.g.
# setUp:
#   self.patcher = patch("openbook_notifications.helpers._send_notification_to_user")
#   self.mock_foo = self.patcher.start()
# tearDown:
#   self.patcher.stop()


class OpenbookAPITestCase(APITransactionTestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass
