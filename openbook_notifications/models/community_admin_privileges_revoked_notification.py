from uuid import UUID
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from openbook_common.models import ModelWithUUID
from openbook_auth.models import User
from openbook_communities.models import Community
from openbook_notifications.models.notification import Notification


class CommunityAdminPrivilegesRevokedNotification(ModelWithUUID):
    notification = GenericRelation(Notification)
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="+")
    revoked_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")

    @classmethod
    def create_community_admin_privileges_revoked_notification(
        cls, community_id: UUID, user_id: UUID
    ) -> "CommunityAdminPrivilegesRevokedNotification":
        admin_privileges_revoked_notification = cls.objects.create(revoked_user_id=user_id, community_id=community_id)
        Notification.create_notification(
            type=Notification.COMMUNITY_ADMIN_PRIVILEGES_REVOKED,
            content_object=admin_privileges_revoked_notification,
            owner_id=user_id,
        )
        return admin_privileges_revoked_notification

    def get_options(self):
        return {"user": self.revoked_user, "space": self.community}
