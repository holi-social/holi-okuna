from feed_posts.checkers import FeedPostChecker
from feed_posts.repositories import FeedPostRepository
from openbook_terms.models import FeedPostCategory


class FeedPostService:
    def __init__(self):
        self.repository = FeedPostRepository()
        self.checker = FeedPostChecker()

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

    def get_feed_posts_by_user_id(self, user_id):
        return self.repository.get_feed_posts_by_user_id(user_id)

    def get_feed_post(self, user, id_or_slug):
        post = self.repository.get_feed_post(id_or_slug)
        self.checker.check_can_query_registered_users_only_feed_posts(user=user, post=post)
        return self.repository.get_feed_post(id_or_slug)
