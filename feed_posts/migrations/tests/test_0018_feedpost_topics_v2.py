from importlib import import_module
import pytest
from django.apps import apps
from django.db import connection
from feed_posts.models import FeedPost
from openbook_common.tests.helpers import make_feed_post, make_topic

# Required because of file name starting with a number
migration = import_module("feed_posts.migrations.0018_feedpost_topics_v2")


@pytest.mark.django_db
class TestMigrateFeedPostTopic:
    def test_migrate_feedpost_topics(self):
        # GIVEN a feed post with only V1 topics
        topics_v1 = [make_topic(slug="eco-tourism"), make_topic(slug="elderly-people")]
        feed_post = make_feed_post()
        feed_post.topics.set(topics_v1)

        # WHEN migrating feed post topics from V1 to V2
        migration.migrate_feed_post_topics(apps, connection.schema_editor())

        # THEN the feed post has mapped V2 topics
        updated_feed_post = FeedPost.objects.get(id=feed_post.id)
        assert sorted(updated_feed_post.topics_v2) == sorted(["lifestyle-consumption", "elderly-care"])
