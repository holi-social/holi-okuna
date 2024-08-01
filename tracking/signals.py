from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from comments.models import Comment
from feed_posts.models import FeedPost
from openbook_appointments.models import Appointment
from openbook_auth.models import User
from openbook_communities.models import Community, Task
from openbook_insights.models import Discussion as InsightDiscussion
from openbook_posts.models import Post
from tracking.event import Event
from tracking.tracking import track_event


# ---- users ----
@receiver(post_save, sender=User)
def track_user_save(sender, instance, created, **kwargs):
    if created:
        track_event(instance, Event.USER_CREATED)
    else:
        track_event(instance, Event.USER_UPDATED)


@receiver(post_delete, sender=User)
def track_user_delete(sender, instance, **kwargs):
    track_event(instance, Event.USER_DELETED)


@receiver(post_delete, sender=Community)
def track_community_delete(sender, instance, **kwargs):
    track_event(instance.creator, Event.SPACE_DELETED)


# ---- posts ----
@receiver(post_save, sender=Post)
def track_post_save(sender, instance, created, **kwargs):
    if created:
        if instance.community:
            track_event(instance.creator, Event.SPACE_POST_CREATED)
        else:
            # TODO posts that are not associated with a community might not be used at the moment
            # as I understand they were used in the past and we might use them again in the future
            track_event(instance.creator, Event.POST_CREATED)
    else:
        if instance.community:
            track_event(instance.creator, Event.SPACE_POST_UPDATED)
        else:
            # TODO posts that are not associated with a community might not be used at the moment
            # as I understand they were used in the past and we might use them again in the future
            track_event(instance.creator, Event.POST_UPDATED)


@receiver(post_delete, sender=Post)
def track_post_delete(sender, instance, **kwargs):
    if instance.community:
        track_event(instance.creator, Event.SPACE_POST_DELETED)
    else:
        # TODO posts that are not associated with a community might not be used at the moment
        # as I understand they were used in the past and we might use them again in the future
        track_event(instance.creator, Event.POST_DELETED)


# --- feed posts ----
@receiver(post_save, sender=FeedPost)
def track_feed_post_save(sender, instance, created, **kwargs):
    if created:
        track_event(instance.creator, Event.FEED_POST_CREATED)
    else:
        track_event(instance.creator, Event.FEED_POST_UPDATED)


@receiver(post_delete, sender=FeedPost)
def track_feed_post_delete(sender, instance, **kwargs):
    track_event(instance.creator, Event.FEED_POST_DELETED)


# ---- comments ----
@receiver(post_save, sender=Comment)
def track_comment_save(sender, instance, created, **kwargs):
    if created:
        if instance.commentable_type == ContentType.objects.get_for_model(Post) and instance.commentable.community:
            track_event(instance.commenter, Event.SPACE_POST_COMMENT_CREATED)
        elif instance.commentable_type == ContentType.objects.get_for_model(Post):
            # TODO posts that are not associated with a community might not be used at the moment
            # as I understand they were used in the past and we might use them again in the future
            track_event(instance.commenter, Event.POST_COMMENT_CREATED)
        elif instance.commentable_type == ContentType.objects.get_for_model(FeedPost):
            track_event(instance.commenter, Event.FEED_POST_COMMENT_CREATED)
        elif instance.commentable_type == ContentType.objects.get_for_model(InsightDiscussion):
            track_event(instance.commenter, Event.INSIGHT_DISCUSSION_COMMENT_CREATED)
    else:
        if instance.commentable_type == ContentType.objects.get_for_model(Post) and instance.commentable.community:
            track_event(instance.commenter, Event.SPACE_POST_COMMENT_UPDATED)
        elif instance.commentable_type == ContentType.objects.get_for_model(Post):
            # TODO posts that are not associated with a community might not be used at the moment
            # as I understand they were used in the past and we might use them again in the future
            track_event(instance.commenter, Event.POST_COMMENT_UPDATED)
        elif instance.commentable_type == ContentType.objects.get_for_model(FeedPost):
            track_event(instance.commenter, Event.FEED_POST_COMMENT_UPDATED)
        elif instance.commentable_type == ContentType.objects.get_for_model(InsightDiscussion):
            track_event(instance.commenter, Event.INSIGHT_DISCUSSION_COMMENT_UPDATED)


@receiver(post_delete, sender=Comment)
def track_comment_delete(sender, instance, **kwargs):
    if instance.commentable_type == ContentType.objects.get_for_model(Post) and instance.commentable.community:
        track_event(instance.commenter, Event.SPACE_POST_COMMENT_DELETED)
    elif instance.commentable_type == ContentType.objects.get_for_model(Post):
        # TODO posts that are not associated with a community might not be used at the moment
        # as I understand they were used in the past and we might use them again in the future
        track_event(instance.commenter, Event.POST_COMMENT_DELETED)
    elif instance.commentable_type == ContentType.objects.get_for_model(FeedPost):
        track_event(instance.commenter, Event.FEED_POST_COMMENT_DELETED)
    elif instance.commentable_type == ContentType.objects.get_for_model(InsightDiscussion):
        track_event(instance.commenter, Event.INSIGHT_DISCUSSION_COMMENT_DELETED)


# ---- appointments ----
@receiver(post_save, sender=Appointment)
def track_appointment_save(sender, instance, created, **kwargs):
    if created:
        track_event(instance.creator, Event.APPOINTMENT_CREATED)
    elif not instance.is_deleted:
        track_event(instance.creator, Event.APPOINTMENT_UPDATED)
    else:
        track_event(instance.creator, Event.APPOINTMENT_DELETED)


@receiver(post_delete, sender=Appointment)
def track_appointment_delete(sender, instance, **kwargs):
    track_event(instance.creator, Event.APPOINTMENT_DELETED)


# ---- comunity tasks ----
@receiver(post_save, sender=Task)
def track_community_task_save(sender, instance, created, **kwargs):
    if created:
        track_event(instance.creator, Event.SPACE_TASK_CREATED)
    elif not instance.is_deleted:
        track_event(instance.creator, Event.SPACE_TASK_UPDATED)
    else:
        track_event(instance.creator, Event.SPACE_TASK_DELETED)


@receiver(post_delete, sender=Task)
def track_community_task_delete(sender, instance, **kwargs):
    track_event(instance.creator, Event.SPACE_TASK_DELETED)
