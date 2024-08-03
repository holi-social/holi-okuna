import sys
from dataclasses import dataclass
from typing import Protocol, Dict
from logging import getLogger

from django.conf import settings
from posthog import Posthog

logger = getLogger("tracking")

posthog: Posthog | None = None


@dataclass
class Event:
    name: str
    properties: Dict[str, str]
    event_version__major: int
    event_version__minor: int
    event_version__patch: int


@dataclass
class PostHogConfig:
    api_key: str
    host: str
    disable_for_testing: bool


class TrackingUser(Protocol):
    username: str
    tracking_consent_analytics: bool
    tracking_consent_personalization: bool


def initialize_tracking(config: PostHogConfig):
    if config.api_key and config.host:
        global posthog
        posthog = Posthog(
            api_key=config.api_key,
            host=config.host,
            debug=settings.DEBUG,
            disabled=config.disable_for_testing,
        )
    else:
        logger.info("POSTHOG_API_KEY and/or POSTHOG_HOST are not set, disabling tracking")


def track_event(user: TrackingUser, event: Event):
    if posthog is not None and user.tracking_consent_analytics:
        logger.debug("track_event %s", event)
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
