from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from openbook_common.models import ModelWithUUID
from openbook_communities.models import CommunityInvite
from openbook_notifications.models.notification import Notification


class CommunityInviteNotification(ModelWithUUID):
    notification = GenericRelation(Notification)
    community_invite = models.ForeignKey(CommunityInvite, on_delete=models.CASCADE)

    @classmethod
    def create_community_invite_notification(cls, community_invite_id, owner_id):
        community_invite_notification = cls.objects.create(community_invite_id=community_invite_id)
        Notification.create_notification(
            type=Notification.COMMUNITY_INVITE,
            content_object=community_invite_notification,
            owner_id=owner_id,
        )
        return community_invite_notification

    @classmethod
    def delete_community_invite_notification(cls, community_invite_id, owner_id):
        cls.objects.filter(community_invite_id=community_invite_id, notification__owner_id=owner_id).delete()

    def get_options(self):
        return {
            "space": self.community_invite.community,
            "user": self.community_invite.creator,
        }
