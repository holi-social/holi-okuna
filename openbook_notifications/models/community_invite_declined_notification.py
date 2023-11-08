from uuid import UUID
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from openbook_common.models import ModelWithUUID
from openbook_auth.models import User
from openbook_communities.models import Community
from openbook_notifications.models.notification import Notification
from openbook_notifications.toggles import mute_notifications


class CommunityInviteDeclinedNotification(ModelWithUUID):
    notification = GenericRelation(Notification)
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="+")
    invitee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")

    @classmethod
    @mute_notifications
    def create_community_invite_declined_notification(
        cls, owner_id: UUID, community_id: UUID, invitee_id: UUID
    ) -> "CommunityInviteDeclinedNotification":
        invite_declined_notification = cls.objects.create(invitee_id=invitee_id, community_id=community_id)
        Notification.create_notification(
            type=Notification.COMMUNITY_INVITE_DECLINED,
            content_object=invite_declined_notification,
            owner_id=owner_id,
        )
        return invite_declined_notification

    def get_options(self):
        return {"user": self.invitee, "space": self.community}
