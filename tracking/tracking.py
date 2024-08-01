import sys

from posthog import Posthog

from openbook.settings import POSTHOG_API_KEY, POSTHOG_HOST
from tracking.event import Event

posthog: Posthog | None = None


def initialize():
    # print(f"initialize {POSTHOG_API_KEY} {POSTHOG_HOST}", file=sys.stderr)
    if POSTHOG_API_KEY and POSTHOG_HOST:
        global posthog
        posthog = Posthog(
            api_key=POSTHOG_API_KEY,
            host=POSTHOG_HOST,
            debug=True,  # TODO disable
            disabled=hasattr(sys, "_called_from_test"),  # don't actually send events in the context of unit testing
        )


def track_event(user, event: Event):
    # print(f"track_event {event} {posthog} {user}", file=sys.stderr)
    if posthog is not None and user.tracking_consent_analytics:
        # print(f"track_event capture {event}", file=sys.stderr)
        posthog.capture(
            distinct_id=user.username,
            event=event.value.name,
            properties={
                **event.value.properties,
                "event_version__major": event.value.event_version__major,
                "event_version__minor": event.value.event_version__minor,
                "event_version__patch": event.value.event_version__patch,
                "trackingConsentAnalytics": user.tracking_consent_analytics,
                "trackingConsentPersonalization": user.tracking_consent_personalization,
            },
        )
