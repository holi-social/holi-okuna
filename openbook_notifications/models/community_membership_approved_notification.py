from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from openbook_common.models import ModelWithUUID
from openbook_auth.models import User
from openbook_communities.models import Community
from openbook_notifications.models.notification import Notification


class CommunityMembershipApprovedNotification(ModelWithUUID):
    notification = GenericRelation(Notification)
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="+")
    approved_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")

    @classmethod
    def create_community_membership_approved_notification(cls, owner_id, community_id, user_id):
        membership_accepted_notification = cls.objects.create(approved_user_id=user_id, community_id=community_id)
        Notification.create_notification(
            type=Notification.COMMUNITY_MEMBERSHIP_APPROVED,
            content_object=membership_accepted_notification,
            owner_id=owner_id,
        )
        return membership_accepted_notification

    def get_options(self):
        return {"user": self.approved_user, "space": self.community}
