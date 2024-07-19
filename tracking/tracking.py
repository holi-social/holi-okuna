from posthog import Posthog

from openbook.settings import POSTHOG_API_KEY, POSTHOG_HOST
from tracking.event import Event

posthog: Posthog | None = None


def initialize():
    if POSTHOG_API_KEY and POSTHOG_HOST:
        global posthog
        posthog = Posthog(
            api_key=POSTHOG_API_KEY,
            host=POSTHOG_HOST,
            debug=True,  # TODO disable
        )


def track_event(user, event: Event):
    if posthog is not None and user.tracking_consent_analytics:
        posthog.capture(
            distinct_id=user.username,
            event=event.value,
            properties={
                "trackingConsentAnalytics": user.tracking_consent_analytics,
                "trackingConsentPersonalization": user.tracking_consent_personalization,
            },
        )
