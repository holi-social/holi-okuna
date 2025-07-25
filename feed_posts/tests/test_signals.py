import pytest
from unittest.mock import patch, Mock, create_autospec

from feed_posts.models import FeedPost
from feed_posts.signals import publish_feed_post_created


@patch("feed_posts.signals.publish_to_okuna_topic")
def test_publish_feed_post_created_does_not_publish_on_update(publish: Mock):
    publish_feed_post_created(sender="feed_posts.FeedPost", instance=create_autospec(FeedPost), created=False)
    publish.assert_not_called()


@patch("feed_posts.signals.publish_to_okuna_topic")
def test_publish_feed_post_created_publishes_on_create(publish: Mock):
    publish_feed_post_created(sender="feed_posts.FeedPost", instance=create_autospec(FeedPost), created=True)
    publish.assert_called_once()


@patch("feed_posts.signals.publish_to_okuna_topic")
def test_publish_feed_post_created_without_category_publishes_correctly(publish: Mock):
    feed_post = create_autospec(FeedPost)
    feed_post.category = None

    publish_feed_post_created(sender="feed_posts.FeedPost", instance=feed_post, created=True)
    publish.assert_called_once()


@patch("feed_posts.signals.publish_to_okuna_topic")
def test_publish_feed_post_created_raises_on_wrong_instance(publish: Mock):
    with pytest.raises(ValueError):
        publish_feed_post_created(sender="feed_posts.FeedPost", instance=None, created=True)
    publish.assert_not_called()
