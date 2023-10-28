from openbook_communities.models import Community as CommunityModel
from openbook_notifications.notifications import (
    SpaceMembershipRequestNotification,
    SpaceMembershipRequestApprovalNotification,
)
from openbook_notifications.payloads import SpaceMembershipRequestPayload, SpaceMembershipRequestApprovalPayload


def notify_space_admins_of_membership_request(user, message, space):
    space_admins = CommunityModel.get_community_with_name_administrators(community_name=space.name)
    recipients = [str(admin.username) for admin in space_admins]
    payload = SpaceMembershipRequestPayload(space=space, user=user, message=message)
    notification = SpaceMembershipRequestNotification(recipients=recipients, payload=payload)
    notification.send()


def notify_space_membership_request_approved(user, space):
    payload = SpaceMembershipRequestApprovalPayload(user, space)
    notification = SpaceMembershipRequestApprovalNotification(recipient=user, payload=payload)
    notification.send()
