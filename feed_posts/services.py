from feed_posts.repositories import FeedPostRepository
from openbook_terms.models import FeedPostCategory


class FeedPostService:
    def __init__(self):
        self.repository = FeedPostRepository()

    def create_feed_post(
        self,
        title,
        visibility,
        description,
        category_id,
        creator,
        image,
        topic_ids=None,
    ):
        category = FeedPostCategory.objects.get(id=category_id)

        return self.repository.create_feed_post(
            title=title,
            visibility=visibility,
            description=description,
            category=category,
            creator=creator,
            image=image,
            topics=topic_ids,
        )

    def get_feed_posts_by_user(self, user):
        return self.repository.get_feed_posts_by_user(user)
