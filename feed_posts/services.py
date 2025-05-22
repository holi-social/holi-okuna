import uuid

from feed_posts.checkers import FeedPostChecker
from feed_posts.models import FeedPostMention
from feed_posts.repositories import FeedPostReactionRepository, FeedPostRepository
from openbook_auth.models import User
from openbook_common.helpers import extract_urls_from_string
from openbook_common.models import LinkPreview
from openbook_common.tracking import TrackingEvent, track
from openbook_common.utils.helpers import extract_usernames_from_string
from openbook_notifications.services import NotificationsService
from openbook_terms.models import FeedPostCategory


class FeedPostService:
    def __init__(self):
        self.repository = FeedPostRepository()
        self.checker = FeedPostChecker()
        self.mention_service = FeedPostMentionService()

    def create_feed_post(
        self,
        title,
        visibility,
        description,
        creator,
        image,
        category_id=None,
        topic_ids=None,
        topics_v2=None,
        language=None,
        location=None,
        geolocation=None,
        images=None,
        image_urls=None,
        aspect_ratio=None,
    ):
        category = FeedPostCategory.objects.get(id=category_id) if category_id else None

        urls = extract_urls_from_string(description)

        link_preview = LinkPreview.from_url(urls[0]) if len(urls) > 0 else None

        post = self.repository.create_feed_post(
            title=title,
            visibility=visibility,
            description=description,
            category=category,
            creator=creator,
            image=image,
            topic_ids=topic_ids,
            topics_v2=topics_v2,
            link_preview=link_preview,
            language=language,
            location=location,
            geolocation=geolocation,
            images=images,
            image_urls=image_urls,
            aspect_ratio=aspect_ratio,
        )

        self.mention_service.add_mentions(post_id=post.id, description=description, creator=creator)

        track(
            creator,
            TrackingEvent(
                "feedPostCreated",
                {
                    "postId": str(post.id),
                    "locations": 0 if geolocation is None else 1,
                    "categories": 0 if category is None else 1,
                    "images": 0 if images is None else len(images),
                    "topics": len(topic_ids or topics_v2 or []),
                },
            ),
        )

        return post

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
        topics_v2=None,
        image=None,
        remove_image=False,
        language=None,
        location=None,
        geolocation=None,
        new_images=None,
        existing_images=None,
        image_urls=None,
        aspect_ratio=None,
    ):
        post = self.repository.get_feed_post(id_or_slug=str(post_id))

        self.checker.check_can_update_feed_post(user=user, post=post)

        category = FeedPostCategory.objects.get(id=category_id) if category_id else None

        urls = extract_urls_from_string(description)

        link_preview = LinkPreview.from_url(urls[0]) if len(urls) > 0 else None

        self.mention_service.add_mentions(post_id=post.id, description=description, creator=user)

        return self.repository.update_feed_post(
            post_id=post_id,
            title=title,
            description=description,
            visibility=visibility,
            category=category,
            topic_ids=topic_ids,
            topics_v2=topics_v2,
            image=image,
            remove_image=remove_image,
            link_preview=link_preview,
            language=language,
            location=location,
            geolocation=geolocation,
            new_images=new_images,
            existing_images=existing_images,
            image_urls=image_urls,
            aspect_ratio=aspect_ratio,
        )

    def get_feed_posts(self):
        return self.repository.get_feed_posts()

    def delete_feed_post(self, user, post_id):
        post = self.repository.get_feed_post(id_or_slug=str(post_id))
        self.checker.check_can_delete_feed_post(user=user, post=post)
        self.mention_service.delete_mentions(post_id=post_id)
        return self.repository.delete_feed_post(post_id)


class FeedPostReactionService:
    def __init__(self):
        self.repository = FeedPostReactionRepository()

    def get_reaction_by_user(self, feed_post, reactor):
        return self.repository.get_reaction_by_user(feed_post=feed_post, reactor=reactor)

    def create_reaction(self, feed_post, reactor, reaction_type):
        reaction = self.repository.create_reaction(feed_post=feed_post, reactor=reactor, reaction_type=reaction_type)
        if reactor.id != feed_post.creator.id:
            NotificationsService.send_post_reaction_notification(
                post=feed_post, reactor=reactor, recipient=feed_post.creator
            )
        return reaction

    def remove_reaction(self, feed_post, reactor, reaction_type):
        return self.repository.remove_reaction(feed_post=feed_post, reactor=reactor, reaction_type=reaction_type)

    def count(self, post_id, reactor_id=None, reaction_type=None):
        return self.repository.count(post_id=post_id, reactor_id=reactor_id, reaction_type=reaction_type)


class FeedPostMentionService:
    def get_mentions(self, post_id: uuid.UUID):
        mention_ids = (
            FeedPostMention.objects.filter(feed_post__id=post_id).values_list("mention", flat=True).distinct()
        )
        return User.objects.filter(id__in=mention_ids)

    def delete_mentions(self, post_id: uuid.UUID):
        return FeedPostMention.objects.filter(feed_post__id=post_id).delete()

    def add_mentions(self, post_id: uuid.UUID, description: str, creator: User):
        self.delete_mentions(post_id=post_id)

        usernames = [username.lower() for username in extract_usernames_from_string(string=description)]
        mentions = User.objects.filter(username__in=usernames).exclude(id=creator.id)

        return FeedPostMention.objects.bulk_create(
            [FeedPostMention(feed_post_id=post_id, mention=mention) for mention in mentions]
        )
