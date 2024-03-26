from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from openbook_auth.models import User, get_reactions
from openbook_common.helpers import (
    PQ,
    attr_filled,
    get_language_for_text,
)
from openbook_common.models import (
    Language,
    LinkPreview,
    ModelWithUUID,
)
from openbook_common.utils.helpers import (
    extract_hashtags_from_string,
    extract_usernames_from_string,
)
from openbook_common.utils.model_loaders import (
    get_comment_user_mention_model,
    get_hashtag_model,
    get_moderated_object_model,
    get_post_comment_notification_model,
    get_post_comment_reaction_notification_model,
    get_post_comment_reply_notification_model,
    get_post_comment_user_mention_notification_model,
    get_user_model,
)
from openbook_moderation.models import ModeratedObject
from openbook_posts.validators import post_comment_text_validators

from .comment_reaction import CommentReaction


class Comment(ModelWithUUID):
    moderated_object = GenericRelation(ModeratedObject, related_query_name="post_comments")

    commentable_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    commentable_id = models.UUIDField()
    commentable = GenericForeignKey("commentable_type", "commentable_id")

    parent_comment = models.ForeignKey("self", on_delete=models.CASCADE, related_name="replies", null=True, blank=True)
    created = models.DateTimeField(editable=False, db_index=True)
    modified = models.DateTimeField(db_index=True, default=timezone.now)
    commenter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="posts_comments")
    text = models.TextField(
        _("text"),
        max_length=settings.POST_COMMENT_MAX_LENGTH,
        blank=False,
        null=False,
        validators=post_comment_text_validators,
    )
    language = models.ForeignKey(Language, on_delete=models.SET_NULL, null=True, related_name="post_comments")
    is_edited = models.BooleanField(default=False, null=False, blank=False)
    # This only happens if the comment was reported and found with critical severity content
    is_deleted = models.BooleanField(default=False)
    links = models.ManyToManyField(LinkPreview, through="CommentLinks", related_name="+", blank=True)

    mentions = models.ManyToManyField(
        User,
        related_name="mentioned_in_comments",
        blank=True,
        through="CommentUserMention",
    )

    class Meta:
        indexes = [
            models.Index(fields=["commentable_type", "commentable_id"]),
        ]
        db_table = "openbook_posts_postcomment"

    @classmethod
    def create_comment(cls, text, commenter, post, parent_comment=None):
        post_comment = Comment.objects.create(
            text=text,
            commenter=commenter,
            commentable=post,
            parent_comment=parent_comment,
            language=get_language_for_text(text),
        )

        return post_comment

    @classmethod
    def count_comments_for_post_with_id(cls, post_id):
        count_query = Q(commentable_id=post_id, parent_comment__isnull=True, is_deleted=False)

        return cls.objects.filter(count_query).count()

    @classmethod
    def get_reaction_counts_for_post_comment_with_id(cls, post_comment_id, reaction_type=None, reactor_id=None):
        reactions_query = Q(
            post_comment_id=post_comment_id,
        )

        if reaction_type:
            reactions_query.add(Q(reaction_type=reaction_type), Q.AND)

        if reactor_id:
            reactions_query.add(Q(reactor__id=reactor_id), Q.AND)

        return get_reactions(CommentReaction, reactions_query)

    def count_replies(self):
        return self.replies.count()

    def count_reactions(self):
        return self.reactions.count()

    def count_mentions(self):
        return self.mentions.count()

    def count_links(self):
        return self.links.count()

    def count_replies_with_user(self, user):
        # Count replies excluding users blocked by authenticated user
        count_query = ~Q(
            Q(commenter__blocked_by_users__blocker_id=user.pk) | Q(commenter__user_blocks__blocked_user_id=user.pk)
        )

        if self.commentable.community:
            if not user.is_staff_of_community_with_name(community_name=self.commentable.community.name):
                # Don't retrieve comments except from staff members
                blocked_users_query_staff_members = Q(
                    commenter__communities_memberships__community_id=self.commentable.community.pk
                )
                blocked_users_query_staff_members.add(
                    Q(commenter__communities_memberships__is_administrator=True)
                    | Q(commenter__communities_memberships__is_moderator=True),
                    Q.AND,
                )

                count_query.add(~blocked_users_query_staff_members, Q.AND)

            # Don't count items that have been reported and approved by community moderators
            ModeratedObject = get_moderated_object_model()
            count_query.add(~Q(moderated_object__status=ModeratedObject.STATUS_APPROVED), Q.AND)

        # Don't count soft deleted items
        count_query.add(Q(is_deleted=False), Q.AND)

        return self.replies.filter(count_query).count()

    def reply_to_comment(self, commenter, text):
        post_comment = Comment.create_comment(
            text=text,
            commenter=commenter,
            post=self.post,
            parent_comment=self,
        )

        return post_comment

    def react(self, reactor, reaction_type):
        return CommentReaction.create_reaction(reactor=reactor, reaction_type=reaction_type, comment=self)

    def clear_reaction(self, reactor, reaction_type):
        return CommentReaction.remove_reaction(reactor=reactor, reaction_type=reaction_type, comment=self)

    def save(self, *args, **kwargs):
        """On save, update timestamps"""
        if not self.created:
            self.created = timezone.now()

        self.modified = timezone.now()

        self.full_clean(exclude=["language"])

        post_comment = super(Comment, self).save(*args, **kwargs)

        self._process_post_comment_mentions()
        self._process_post_comment_hashtags()
        self._process_post_comment_links()

        return post_comment

    def _process_post_comment_mentions(self):
        usernames = extract_usernames_from_string(string=self.text)

        if not usernames:
            self.mentions.clear()
        else:
            existing_mention_usernames = []
            for existing_mention in self.mentions.all().iterator():
                existing_mention_username = existing_mention.username.lower()
                if existing_mention_username not in usernames:
                    existing_mention.delete()
                else:
                    existing_mention_usernames.append(existing_mention_username)

            CommentUserMention = get_comment_user_mention_model()
            User = get_user_model()

            for username in usernames:
                username = username.lower()
                if username not in existing_mention_usernames:
                    try:
                        user = User.objects.only("id", "username").get(username__iexact=username)

                        user_can_see_post_comment = user.can_see_post_comment(post_comment=self)
                        user_is_commenter = user.pk == self.commenter_id
                        if not user_is_commenter:
                            CommentUserMention.create_post_comment_user_mention(
                                user=user,
                                post_comment=self,
                                notify=user_can_see_post_comment,
                            )
                            existing_mention_usernames.append(username)
                    except User.DoesNotExist:
                        pass

    def _process_post_comment_hashtags(self):
        if not self.text:
            self.hashtags.all().delete()
        else:
            hashtags = extract_hashtags_from_string(string=self.text)
            if not hashtags:
                self.hashtags.all().delete()
            else:
                existing_hashtags = []
                for existing_hashtag in self.hashtags.only("id", "name").all().iterator():
                    if existing_hashtag.name not in hashtags:
                        self.hashtags.remove(existing_hashtag)
                    else:
                        existing_hashtags.append(existing_hashtag.name)

                Hashtag = get_hashtag_model()

                for hashtag in hashtags:
                    hashtag = hashtag.lower()
                    if hashtag not in existing_hashtags:
                        hashtag_obj = Hashtag.get_or_create_hashtag(name=hashtag)
                        self.hashtags.add(hashtag_obj)

    def _process_post_comment_links(self):
        if self.has_text():
            self.links.set(LinkPreview.parse_text(self.text))
        else:
            self.links.clear()

    def update_comment(self, text):
        self.text = text
        self.is_edited = True
        self.language = get_language_for_text(text)
        self.save()

    def soft_delete(self):
        self.is_deleted = True
        self.delete_notifications()
        self.save()

    def unsoft_delete(self):
        self.is_deleted = False
        self.save()

    def delete_notifications(self):
        # Delete all post comment notifications
        PostCommentNotification = get_post_comment_notification_model()
        PostCommentNotification.objects.filter(post_comment_id=self.pk).delete()

        # Delete all post comments reply notifications
        PostCommentReplyNotification = get_post_comment_reply_notification_model()
        PostCommentReplyNotification.objects.filter(post_comment__parent_comment_id=self.pk).delete()

        # Delete all post comment reaction notifications
        PostCommentReactionNotification = get_post_comment_reaction_notification_model()
        PostCommentReactionNotification.objects.filter(post_comment_reaction__post_comment_id=self.pk).delete()

        # Delete all post comment reply reaction notifications
        PostCommentReactionNotification = get_post_comment_reaction_notification_model()
        PostCommentReactionNotification.objects.filter(
            post_comment_reaction__post_comment__parent_comment_id=self.pk
        ).delete()

        # Delete all post comment user mention notifications
        PostCommentUserMentionNotification = get_post_comment_user_mention_notification_model()
        PostCommentUserMentionNotification.objects.filter(
            post_comment_user_mention__post_comment__commentable_id=self.pk
        ).delete()

    def delete_notifications_for_user(self, user):
        # Delete all post comment notifications
        PostCommentNotification = get_post_comment_notification_model()
        PostCommentNotification.objects.filter(post_comment_id=self.pk, notification__owner_id=user.pk).delete()

        # Delete all post comments reply notifications
        PostCommentReplyNotification = get_post_comment_reply_notification_model()
        PostCommentReplyNotification.objects.filter(
            post_comment__parent_comment_id=self.pk, notification__owner_id=user.pk
        ).delete()

        # Delete all post comment reaction notifications
        PostCommentReactionNotification = get_post_comment_reaction_notification_model()
        PostCommentReactionNotification.objects.filter(
            post_comment_reaction__post_comment_id=self.pk,
            notification__owner_id=user.pk,
        ).delete()

        # Delete all post comment reply reaction notifications
        PostCommentReactionNotification = get_post_comment_reaction_notification_model()
        PostCommentReactionNotification.objects.filter(
            notification__owner_id=user.pk,
            post_comment_reaction__post_comment__parent_comment_id=self.pk,
        ).delete()

        # Delete all post comment user mention notifications
        PostCommentUserMentionNotification = get_post_comment_user_mention_notification_model()
        PostCommentUserMentionNotification.objects.filter(
            post_comment_user_mention__post_comment__commentable_id=self.pk,
            notification__owner_id=user.pk,
        ).delete()

    def has_text(self):
        return attr_filled(self, "text")

    @staticmethod
    def is_visible_query(user, prefix=None):
        return PQ(prefix, is_deleted=False)


class CommentLinks(models.Model):
    linkpreview = models.ForeignKey("openbook_common.LinkPreview", on_delete=models.CASCADE)
    postcomment = models.ForeignKey(Comment, db_column="postcomment_id", on_delete=models.CASCADE)

    class Meta:
        db_table = "openbook_posts_postcomment_links"
