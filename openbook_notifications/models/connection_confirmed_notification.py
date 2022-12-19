from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models import Q

from openbook_auth.models import User
from openbook_common.models import ModelWithUUID
from openbook_notifications.models.connection_accepted_notification import (
    ConnectionAcceptedNotification,
)
from openbook_notifications.models.notification import Notification


class ConnectionConfirmedNotification(ModelWithUUID):
    notification = GenericRelation(Notification)
    connection_confirmator = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="+"
    )

    @classmethod
    def create_connection_confirmed_notification(
        cls, connection_confirmator_id, owner_id
    ):
        connection_confirmed_notification = cls.objects.create(
            connection_confirmator_id=connection_confirmator_id
        )
        Notification.create_notification(
            type=Notification.CONNECTION_CONFIRMED,
            content_object=connection_confirmed_notification,
            owner_id=owner_id,
        )
        ConnectionAcceptedNotification.create_connection_accepted_notification(
            connected_user_id=owner_id, owner_id=connection_confirmator_id
        )
        return connection_confirmed_notification

    @classmethod
    def delete_connection_confirmed_notification_for_users_with_ids(
        cls, user_a_id, user_b_id
    ):
        notification_query = Q(
            connection_confirmator_id=user_a_id, notification__owner_id=user_b_id
        ) | Q(connection_confirmator_id=user_b_id, notification__owner_id=user_a_id)

        cls.objects.filter(notification_query).delete()
        ConnectionAcceptedNotification.delete_connection_accepted_notification_for_users_with_ids(
            user_a_id, user_b_id
        )

    def get_options(self):
        return {"user": self.connection_confirmator}
