from feed_posts.models import FeedPost
from openbook_common.utils.helpers import is_uuid


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

    def get_feed_posts_by_user_id(self, user_id):
        return FeedPost.objects.filter(creator_id=user_id)

    def get_feed_post(self, id_or_slug):
        return FeedPost.objects.get(id=id_or_slug) if is_uuid(id_or_slug) else FeedPost.objects.get(slug=id_or_slug)
