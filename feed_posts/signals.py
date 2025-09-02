from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from openbook_common.rewards_api import RewardsClient, Event
from openbook_common.utils.model_loaders import get_feed_post_model

if TYPE_CHECKING:
    from feed_posts.models import FeedPost


@dataclass(frozen=True)
class FeedPostCreatedPayload:
    category: str | None

    def as_dict(self) -> dict:
        return {
            "category": self.category,
        }


class FeedPostCreatedEvent(Event[FeedPostCreatedPayload]):
    pass


def publish_feed_post_created(instance: "FeedPost", created: bool, **kwargs):
    FeedPost = get_feed_post_model()

    # only emit an event on the first creation of the feed post
    if not created:
        return

    if not isinstance(instance, FeedPost):
        raise ValueError("wrong model connected to signal handler")

    event = FeedPostCreatedEvent(
        user_id=UUID(instance.creator.username),
        event_type="FeedPostCreated",
        data=FeedPostCreatedPayload(category=(instance.category.slug if instance.category else None)),
    )

    RewardsClient.submit_event(event)
