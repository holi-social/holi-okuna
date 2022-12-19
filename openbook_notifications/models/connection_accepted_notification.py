from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models import Q
from openbook_auth.models import User
from openbook_common.models import ModelWithUUID
from openbook_notifications.models.notification import Notification


class ConnectionAcceptedNotification(ModelWithUUID):
    notification = GenericRelation(Notification)
    connected_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")

    @classmethod
    def create_connection_accepted_notification(cls, connected_user_id, owner_id):
        connection_accepted_notification = cls.objects.create(
            connected_user_id=connected_user_id
        )
        Notification.create_notification(
            type=Notification.CONNECTION_ACCEPTED,
            content_object=connection_accepted_notification,
            owner_id=owner_id,
        )
        return connection_accepted_notification

    @classmethod
    def delete_connection_accepted_notification_for_users_with_ids(
        cls, user_a_id, user_b_id
    ):
        notification_query = Q(
            connected_user_id=user_a_id, notification__owner_id=user_b_id
        ) | Q(connected_user_id=user_b_id, notification__owner_id=user_a_id)

        cls.objects.filter(notification_query).delete()

    def get_options(self):
        return {"user": self.connected_user}
