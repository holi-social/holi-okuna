import uuid

from django.db.models import Q

from feed_posts.models import FeedPost, FeedPostReaction
from openbook_auth.models import User, get_reactions, UserRole
from openbook_common.enums import ReactionType
from openbook_common.schema.types import GeolocationPointInput
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
        link_preview,
        language,
        location,
        geolocation,
    ):
        if creator.role == UserRole.CO_FOUNDER and category.slug == "founder-update":
            priority_duration = 2
        else:
            priority_duration = 0

        feed_post = FeedPost.objects.create(
            title=title,
            visibility=visibility,
            description=description,
            category=category,
            creator=creator,
            image=image,
            link_preview=link_preview,
            language_code=language,
            location=location,
            geolocation=GeolocationPointInput.to_point(geolocation),
            priority_duration=priority_duration,
        )

        if topics is not None:
            feed_post.topics.set(topics)

        return feed_post

    def get_feed_posts_by_user_id(self, user_id):
        return FeedPost.objects.filter(creator__username=user_id).order_by("-created_at")

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
        link_preview=None,
        language=None,
        location=None,
        geolocation=None,
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

        if language is not None:
            post.language_code = language

        if location is not None:
            post.location = location

        if geolocation is not None:
            post.geolocation = GeolocationPointInput.to_point(geolocation)

        post.link_preview = link_preview

        post.save()

        return post

    def get_feed_posts(self):
        return FeedPost.objects.order_by("-created_at")

    def delete_feed_post(self, post_id):
        return FeedPost.objects.get(id=post_id).delete()


class FeedPostReactionRepository:
    def get_reaction_by_user(self, feed_post: FeedPost, reactor: User):
        return FeedPostReaction.objects.filter(feed_post=feed_post, reactor=reactor).first()

    def create_reaction(self, feed_post: FeedPost, reactor: User, reaction_type: ReactionType):
        FeedPostReaction.objects.filter(feed_post=feed_post, reactor=reactor).delete()
        return FeedPostReaction.objects.create(feed_post=feed_post, reactor=reactor, reaction_type=reaction_type)

    def remove_reaction(self, feed_post: FeedPost, reactor: User, reaction_type: ReactionType):
        return FeedPostReaction.objects.filter(
            feed_post=feed_post, reactor=reactor, reaction_type=reaction_type
        ).delete()

    def count(self, post_id: uuid.UUID, reactor_id: uuid.UUID = None, reaction_type: ReactionType = None):
        reactions_query = Q(
            feed_post_id=post_id,
        )

        if reaction_type:
            reactions_query.add(Q(reaction_type=reaction_type), Q.AND)

        if reactor_id:
            reactions_query.add(Q(reactor__id=reactor_id), Q.AND)

        return get_reactions(FeedPostReaction, reactions_query)
