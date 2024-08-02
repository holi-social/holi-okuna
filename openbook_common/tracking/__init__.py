import sys
from dataclasses import dataclass
from typing import Protocol, Dict

from django.conf import settings
from posthog import Posthog

from openbook.settings import POSTHOG_API_KEY, POSTHOG_HOST

posthog: Posthog | None = None


@dataclass
class Event:
    name: str
    properties: Dict[str, str]
    event_version__major: int
    event_version__minor: int
    event_version__patch: int


class User(Protocol):
    username: str
    tracking_consent_analytics: bool
    tracking_consent_personalization: bool


def initialize_tracking():
    if POSTHOG_API_KEY and POSTHOG_HOST:
        global posthog
        posthog = Posthog(
            api_key=POSTHOG_API_KEY,
            host=POSTHOG_HOST,
            debug=settings.DEBUG,
            disabled=hasattr(sys, "_called_from_test"),  # don't actually send events in the context of unit testing
        )


def track_event(user: User, event: Event):
    if posthog is not None and user.tracking_consent_analytics:
        posthog.capture(
            distinct_id=user.username,
            event=event.name,
            properties={
                **event.properties,
                "event_version__major": event.event_version__major,
                "event_version__minor": event.event_version__minor,
                "event_version__patch": event.event_version__patch,
                "trackingConsentAnalytics": user.tracking_consent_analytics,
                "trackingConsentPersonalization": user.tracking_consent_personalization,
            },
        )
