from feed_posts.models import FeedPost


class FeedPostRepository:
    def create_feed_post(
        self,
        title,
        visibility,
        description,
        topics,
        category,
        creator,
    ):
        feed_post = FeedPost.objects.create(
            title=title,
            visibility=visibility,
            description=description,
            category=category,
            creator=creator,
        )

        feed_post.topics.set(topics)

        return feed_post
