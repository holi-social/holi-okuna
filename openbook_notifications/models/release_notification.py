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

    class Meta:
        ordering = ["-notification__created"]

    def send_to_all_users(self) -> int:
        if self.is_sent:
            raise ValidationError("Notification was already processed")

        self.is_sent = True
        self.save(force_update=True)

        users = User.objects.values_list("id", flat=True)[:]
        for user_id in users:
            Notification.create_notification(
                type=Notification.RELEASE_INFO,
                content_object=self,
                owner_id=user_id,
            )

        return len(users)

    def get_options(self):
        return {"post": self.post}
