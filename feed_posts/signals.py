from functools import partial
from typing import override, TYPE_CHECKING
from openbook_common.pubsub.event import Event
from openbook_common.pubsub.publisher import publish_event
from openbook_common.pubsub.topic import Topic
from openbook_common.utils.model_loaders import get_feed_post_model

if TYPE_CHECKING:
    from feed_posts.models import FeedPost

publish_to_okuna_topic = partial(publish_event, Topic.OKUNA.value)


class FeedPostCreatedEvent(Event):
    def __init__(self, post: "FeedPost"):
        self.post = post
        super().__init__(
            data={"category": self.post.category.slug},
            event_type="FeedPostCreated",
            event_version="1.0.0",
        )

    def log_str(self) -> str:
        return f"PostCreated(post_id={self.post.id})"

    @override
    def to_dict(self) -> dict:
        return super().to_dict() | {
            "userId": self.post.creator.username,
        }


def publish_feed_post_created(instance, created: bool, **kwargs):
    FeedPost = get_feed_post_model()

    # only emit an event on the first creation of the feed post
    if not created:
        return

    if not isinstance(instance, FeedPost):
        raise ValueError("wrong model connected to signal handler")

    publish_to_okuna_topic(FeedPostCreatedEvent(post=instance))
