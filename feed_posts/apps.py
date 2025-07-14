from django.apps import AppConfig
from django.db.models.signals import post_save

from feed_posts.signals import emit_post_created


class FeedPostsConfig(AppConfig):
    name = "feed_posts"

    def ready(self):
        post_save.connect(emit_post_created, sender="feed_posts.FeedPost", dispatch_uid="emit_post_created")
