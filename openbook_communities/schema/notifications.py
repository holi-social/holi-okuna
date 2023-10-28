from openbook_communities.models import Community as CommunityModel
from openbook_notifications.notifications import SpaceMembershipRequestNotification
from openbook_notifications.payloads import SpaceMembershipRequestPayload


class Notifications:
    @staticmethod
    def notify_space_admins_of_membership_request(requesting_user, requesting_user_message, space):
        space_admins = CommunityModel.get_community_with_name_administrators(community_name=space.name)
        recipients = [str(admin.username) for admin in space_admins]
        payload = SpaceMembershipRequestPayload(space=space, user=requesting_user, message=requesting_user_message)
        notification = SpaceMembershipRequestNotification(recipients=recipients, payload=payload)
        notification.send()
