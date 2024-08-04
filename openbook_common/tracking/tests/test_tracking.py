import unittest

from faker import Faker
from unittest import mock
from dataclasses import dataclass

from openbook_common.tracking import TrackingUser, TrackingEvent, track, initialize_tracking, PostHogConfig

faker = Faker()


@dataclass
class UserForTest(TrackingUser):
    username: str
    tracking_consent_analytics: bool
    tracking_consent_personalization: bool


class TestTracking(unittest.TestCase):
    def setUp(self):
        initialize_tracking(PostHogConfig(api_key="fake_api_key", host="fake_host", disable_for_testing=True))

    @mock.patch("posthog.Posthog.capture")
    def test_no_tracking_without_analytics_consent(self, mock_posthog_capture):
        user = UserForTest("donald_trump", False, faker.boolean())
        track(user, TrackingEvent("testEvent"))
        mock_posthog_capture.assert_not_called()

    @mock.patch("posthog.Posthog.capture")
    def test_adds_event_version_and_consent(self, mock_posthog_capture):
        username = "donald_trump"
        consent_analytics = True
        consent_personalization = faker.boolean()
        user = UserForTest(username, consent_analytics, consent_personalization)
        track(user, TrackingEvent("testEvent", {}, 1, 2, 3))
        mock_posthog_capture.assert_called_once_with(
            distinct_id=username,
            event="testEvent",
            properties={
                "event_version__major": 1,
                "event_version__minor": 2,
                "event_version__patch": 3,
                "trackingConsentAnalytics": consent_analytics,
                "trackingConsentPersonalization": consent_personalization,
            },
        )

    @mock.patch("posthog.Posthog.capture")
    def test_adds_event_properties(self, mock_posthog_capture):
        username = "donald_trump"
        consent_analytics = True
        consent_personalization = faker.boolean()
        user = UserForTest(username, consent_analytics, consent_personalization)
        track(user, TrackingEvent("testEvent", {"random_name": "random_value"}, 1, 2, 3))
        mock_posthog_capture.assert_called_once_with(
            distinct_id=username,
            event="testEvent",
            properties={
                "event_version__major": 1,
                "event_version__minor": 2,
                "event_version__patch": 3,
                "trackingConsentAnalytics": consent_analytics,
                "trackingConsentPersonalization": consent_personalization,
                "random_name": "random_value",
            },
        )

    @mock.patch("posthog.Posthog.capture")
    def test_adds_default_properties_and_version(self, mock_posthog_capture):
        user = UserForTest("donald_trump", True, True)
        track(user, TrackingEvent("testEvent"))
        mock_posthog_capture.assert_called_once_with(
            distinct_id=user.username,
            event="testEvent",
            properties={
                "event_version__major": 1,
                "event_version__minor": 0,
                "event_version__patch": 0,
                "trackingConsentAnalytics": True,
                "trackingConsentPersonalization": True,
            },
        )
