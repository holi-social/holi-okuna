import uuid

import pytest
from unittest.mock import patch, Mock, create_autospec

from feed_posts.models import FeedPost
from feed_posts.signals import publish_feed_post_created
from openbook_common.rewards_api import Client


@patch("feed_posts.signals.RewardsClient", autospec=Client)
def test_publish_feed_post_created_does_not_publish_on_update(client: Mock):
    publish_feed_post_created(sender="feed_posts.FeedPost", instance=create_autospec(FeedPost), created=False)
    client.submit_event.assert_not_called()


@patch("feed_posts.signals.RewardsClient", autospec=Client)
def test_publish_feed_post_created_publishes_on_create(client: Mock):
    feed_post = create_autospec(FeedPost)
    feed_post.creator.username = uuid.uuid4().hex

    publish_feed_post_created(sender="feed_posts.FeedPost", instance=feed_post, created=True)
    client.submit_event.assert_called_once()


@patch("feed_posts.signals.RewardsClient", autospec=Client)
def test_publish_feed_post_created_without_category_publishes_correctly(client: Mock):
    feed_post = create_autospec(FeedPost)
    feed_post.category = None
    feed_post.creator.username = uuid.uuid4().hex

    publish_feed_post_created(sender="feed_posts.FeedPost", instance=feed_post, created=True)
    client.submit_event.assert_called_once()


@patch("feed_posts.signals.RewardsClient", autospec=Client)
def test_publish_feed_post_created_raises_on_wrong_instance(client: Mock):
    with pytest.raises(ValueError):
        publish_feed_post_created(sender="feed_posts.FeedPost", instance=None, created=True)
    client.submit_event.assert_not_called()
