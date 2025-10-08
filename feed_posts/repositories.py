import concurrent
import uuid

from django.db.models import Q

from feed_posts.models import FeedPost, FeedPostReaction, FeedPostImage
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
        topics_v2,
        category,
        creator,
        image,
        link_preview,
        language,
        location,
        geolocation,
        images,
        image_urls,
        aspect_ratio,
    ):
        if creator.role == UserRole.CO_FOUNDER and category is not None and category.slug == "founder-update":
            priority_duration = 2
        else:
            priority_duration = 0

        post_image = None

        if image is not None:
            post_image = image
        elif images is not None and len(images) > 0:
            post_image = images[0]["image"]

        if topics_v2 is None:
            topics_v2 = []

        if image_urls is not None:
            image_urls = [url for url in image_urls if url is not None]

        if aspect_ratio is not None:
            aspect_ratio = aspect_ratio

        feed_post = FeedPost.objects.create(
            title=title,
            visibility=visibility,
            description=description,
            category=category,
            creator=creator,
            link_preview=link_preview,
            language_code=language,
            location=location,
            geolocation=GeolocationPointInput.to_point(geolocation),
            priority_duration=priority_duration,
            image=post_image,
            topics_v2=topics_v2,
            image_urls=image_urls,
            aspect_ratio=aspect_ratio,
        )

        # This code is required for backward compatibility. Remove it after version 1.30.x
        if image is not None:
            FeedPostImage.objects.create(feed_post=feed_post, image=image, order=0)

        if images is not None:
            self._add_images(feed_post=feed_post, images=images)

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
        topics_v2=None,
        image=None,
        remove_image=False,
        link_preview=None,
        language=None,
        location=None,
        geolocation=None,
        new_images=None,
        existing_images=None,
        image_urls=None,
        aspect_ratio=None,
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

        if topics_v2 is not None:
            post.topics_v2 = topics_v2

        if image_urls is not None:
            post.image_urls = image_urls

        if aspect_ratio is not None:
            post.aspect_ratio = aspect_ratio

        # This code is required for backward compatibility. Remove it after version 1.30.x
        if remove_image:
            FeedPostImage.objects.filter(feed_post=post).delete()
        elif image:
            q = FeedPostImage.objects.filter(feed_post=post)

            if q.exists():
                q.delete()

            FeedPostImage.objects.create(feed_post=post, image=image, order=0)

        if language is not None:
            post.language_code = language

        if location is not None:
            post.location = location

        if geolocation is not None:
            post.geolocation = GeolocationPointInput.to_point(geolocation)

        if new_images is not None or existing_images is not None:
            self._update_images(feed_post=post, new_images=new_images, existing_images=existing_images)

        post.link_preview = link_preview

        post.save()

        return post

    def get_feed_posts(self):
        return FeedPost.objects.order_by("-created_at")

    def delete_feed_post(self, post_id):
        return FeedPost.objects.get(id=post_id).delete()

    def _add_images(self, feed_post, images):
        def save_image(obj):
            image = FeedPostImage(
                feed_post=feed_post,
                image=obj["image"],
                order=obj["order"],
                alt_text=obj.get("alt_text") or None,
                aspect_ratio=obj.get("aspect_ratio") or None,
            )
            image.save()

        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(save_image, images)

    def _update_images(self, feed_post, new_images, existing_images):
        if existing_images is not None:
            current_images = FeedPostImage.objects.filter(feed_post=feed_post)
            current_image_set = set(current_images.values_list("id", flat=True))

            existing_image_set = set([obj["id"] for obj in existing_images])

            images_to_delete = current_image_set - existing_image_set

            if images_to_delete:
                FeedPostImage.objects.filter(feed_post=feed_post, id__in=images_to_delete).delete()

            images_to_update = current_image_set.intersection(existing_image_set)

            if images_to_update:
                updates = {obj["id"]: obj for obj in existing_images if obj["id"] in images_to_update}
                images = FeedPostImage.objects.filter(feed_post=feed_post, id__in=images_to_update)
                for image in images:
                    image_data = updates.get(image.id)
                    if image_data:
                        image.order = image_data.get("order", image.order)
                        image.alt_text = image_data.get("alt_text", image.alt_text)
                        image.aspect_ratio = image_data.get("aspect_ratio", image.aspect_ratio)
                        image.save()

        if new_images is not None:
            self._add_images(feed_post=feed_post, images=new_images)


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
