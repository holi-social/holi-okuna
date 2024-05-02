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

        if topics is not None:
            feed_post.topics.set(topics)

        return feed_post

    def get_feed_posts_by_user_id(self, user_id):
        return FeedPost.objects.filter(creator__username=user_id)

    def get_feed_post(self, id_or_slug):
        return FeedPost.objects.get(id=id_or_slug) if is_uuid(id_or_slug) else FeedPost.objects.get(slug=id_or_slug)

    def exists(self, post_id):
        return FeedPost.objects.filter(id=post_id).exists()

    def update_feed_post(
        self,
        post_id,
        title=None,
        description=None,
        visibility=None,
        category=None,
        topics=None,
        image=None,
        remove_image=False,
    ):
        post = FeedPost.objects.get(id=post_id)

        if title is not None:
            post.title = title

        if description is not None:
            post.description = description

        if visibility is not None:
            post.visibility = visibility

        if category is not None:
            post.category = category

        if topics is not None:
            post.topics.set(topics)

        if remove_image:
            post.delete_image()
        elif image:
            post.update_image(image)

        post.save()

        return post

    def get_feed_posts(self):
        return FeedPost.objects.order_by("-created_at")

    def delete_feed_post(self, post_id):
        return FeedPost.objects.get(id=post_id).delete()
