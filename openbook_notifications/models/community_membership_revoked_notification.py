from uuid import UUID
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from openbook_common.models import ModelWithUUID
from openbook_auth.models import User
from openbook_communities.models import Community
from openbook_notifications.models.notification import Notification


class CommunityMembershipRevokedNotification(ModelWithUUID):
    notification = GenericRelation(Notification)
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="+")
    revoked_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")

    @classmethod
    def create_community_membership_revoked_notification(
        cls, community_id: UUID, user_id: UUID
    ) -> "CommunityMembershipRevokedNotification":
        membership_revoked_notification = cls.objects.create(revoked_user_id=user_id, community_id=community_id)
        Notification.create_notification(
            type=Notification.COMMUNITY_MEMBERSHIP_REVOKED,
            content_object=membership_revoked_notification,
            owner_id=user_id,
        )
        return membership_revoked_notification

    def get_options(self):
        return {"user": self.revoked_user, "space": self.community}
