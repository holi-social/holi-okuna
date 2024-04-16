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
        image,
    ):
        feed_post = FeedPost.objects.create(
            title=title,
            visibility=visibility,
            description=description,
            category=category,
            creator=creator,
            image=image,
        )

        feed_post.topics.set(topics)

        return feed_post
