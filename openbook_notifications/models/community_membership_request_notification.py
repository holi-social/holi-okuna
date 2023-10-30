from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from openbook_common.models import ModelWithUUID
from openbook_communities.models import CommunityMembershipRequest
from openbook_notifications.models.notification import Notification
from openbook_notifications.toggles import mute_notifications


class CommunityMembershipRequestNotification(ModelWithUUID):
    notification = GenericRelation(Notification)
    membership_request = models.ForeignKey(CommunityMembershipRequest, on_delete=models.CASCADE, related_name="+")

    @classmethod
    @mute_notifications
    def create_community_membership_request_notification(cls, membership_request_id, owner_id):
        membership_request_notification = cls.objects.create(membership_request_id=membership_request_id)
        Notification.create_notification(
            type=Notification.COMMUNITY_MEMBERSHIP_REQUEST,
            content_object=membership_request_notification,
            owner_id=owner_id,
        )
        return membership_request_notification

    def get_options(self):
        return {
            "user": self.membership_request.user,
            "space": self.membership_request.community,
            "message": self.membership_request.message,
        }
