from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from rest_framework.exceptions import ValidationError

from openbook_auth.models import User
from openbook_common.models import OrderedModelWithUUID
from openbook_notifications.models.notification import Notification
from openbook_posts.models import Post


class ReleaseNotification(OrderedModelWithUUID):
    notification = GenericRelation(Notification, related_name="release_notifications")
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    is_sent = models.BooleanField(
        default=False,
        help_text="Designates whether the Notification was already sent to all Users",
        verbose_name="was sent",
    )

    def send_to_all_users(self):
        if self.is_sent:
            raise ValidationError("Notification was already processed")

        self.is_sent = True
        self.save(force_update=True)

        for user_id in User.objects.values_list("id", flat=True)[:]:
            Notification.create_notification(
                type=Notification.RELEASE,
                content_object=self,
                owner_id=user_id,
            )

    def get_options(self):
        return {"post": self.post}
