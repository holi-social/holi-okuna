from feed_posts.checkers import FeedPostChecker
from feed_posts.repositories import FeedPostRepository, FeedPostReactionRepository
from openbook_terms.models import FeedPostCategory, Topic


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
        return post

    def exists(self, post_id):
        return self.repository.exists(post_id)

    def update_feed_post(
        self,
        user,
        post_id,
        title=None,
        description=None,
        visibility=None,
        category_id=None,
        topic_ids=None,
        image=None,
        remove_image=False,
    ):
        post = self.repository.get_feed_post(id_or_slug=str(post_id))

        self.checker.check_can_update_feed_post(user=user, post=post)

        category = FeedPostCategory.objects.get(id=category_id)

        topics = Topic.objects.filter(id__in=topic_ids)

        return self.repository.update_feed_post(
            post_id=post_id,
            title=title,
            description=description,
            visibility=visibility,
            category=category,
            topics=topics,
            image=image,
            remove_image=remove_image,
        )

    def get_feed_posts(self):
        return self.repository.get_feed_posts()

    def delete_feed_post(self, user, post_id):
        post = self.repository.get_feed_post(id_or_slug=str(post_id))
        self.checker.check_can_delete_feed_post(user=user, post=post)
        return self.repository.delete_feed_post(post_id)


class FeedPostReactionService:
    def __init__(self):
        self.repository = FeedPostReactionRepository()

    def get_reaction_by_user(self, feed_post, reactor):
        return self.repository.get_reaction_by_user(feed_post=feed_post, reactor=reactor)

    def create_reaction(self, feed_post, reactor, reaction_type):
        return self.repository.create_reaction(feed_post=feed_post, reactor=reactor, reaction_type=reaction_type)

    def remove_reaction(self, feed_post, reactor, reaction_type):
        return self.repository.remove_reaction(feed_post=feed_post, reactor=reactor, reaction_type=reaction_type)

    def count(self, post_id, reactor_id=None, reaction_type=None):
        return self.repository.count(post_id=post_id, reactor_id=reactor_id, reaction_type=reaction_type)
