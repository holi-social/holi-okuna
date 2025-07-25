from django.apps import AppConfig
from django.db.models.signals import post_save

from feed_posts.signals import publish_feed_post_created


class FeedPostsConfig(AppConfig):
    name = "feed_posts"

    def ready(self):
        post_save.connect(
            publish_feed_post_created, sender="feed_posts.FeedPost", dispatch_uid="publish_feed_post_created"
        )
