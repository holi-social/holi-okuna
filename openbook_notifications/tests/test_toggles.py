import pytest

from django.test import TestCase
from django.db import IntegrityError
from openbook_common.enums import FeatureToggleName, FeatureToggleType
from openbook_common.models import FeatureToggle as FeatureToggleModel
from openbook_notifications.toggles import notifications_toggle


@pytest.mark.django_db
class NotificationsToggleTestCase(TestCase):
    def setUp(self):
        self.notifications_toggle = FeatureToggleModel.objects.create(
            name=FeatureToggleName.NOTIFICATIONS.value, status=FeatureToggleType.PRODUCTION
        )

    def test_notifications_toggle_enabled(self):
        @notifications_toggle
        def test_send_notification():
            return True

        result = test_send_notification()
        self.assertTrue(result)

    def test_notifications_toggle_disabled(self):
        self.notifications_toggle.status = FeatureToggleType.OFF
        self.notifications_toggle.save()

        @notifications_toggle
        def test_send_notification():
            return True

        result = test_send_notification()
        self.assertIsNone(result)

    def test_notifications_toggle_not_exist(self):
        self.notifications_toggle.delete()

        @notifications_toggle
        def test_send_notification():
            return True

        result = test_send_notification()
        self.assertIsNone(result)

    def tearDown(self):
        if self.notifications_toggle.id is not None:
            self.notifications_toggle.delete()
