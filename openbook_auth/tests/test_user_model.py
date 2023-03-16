from unittest import TestCase

from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import PermissionDenied

from openbook_common.tests.assertions import TestAssertionsMixin
from openbook_common.tests.helpers import make_user, make_community
from openbook_notifications.models import Notification


class UserModelTest(TestAssertionsMixin, TestCase):
    def test_approve_membership_denied_for_non_staff_members(self):
        membership_requestor = make_user()
        space_creator = make_user()
        other_user = make_user()

        space = make_community(creator=space_creator)
        membership_requestor.request_membership_to_community_with_name(space.name)

        with self.assertRaises(PermissionDenied):
            other_user.approve_membership_request_to_community_for_username(membership_requestor.username, space.name)

        with self.assertRaises(PermissionDenied):
            membership_requestor.approve_membership_request_to_community_for_username(
                membership_requestor.username, space.name
            )

    def test_approve_membership_request_to_community_for_username(self):
        membership_requestor = make_user()
        space_creator = make_user()
        other_user = make_user()

        space = make_community(creator=space_creator)
        membership_requestor.request_membership_to_community_with_name(space.name)

        # precondition
        self.assertTrue(membership_requestor.is_membership_requestor_of_community_with_name(space.name))

        returned_space = space_creator.approve_membership_request_to_community_for_username(
            membership_requestor.username, space.name
        )

        # postcondition
        self.assertTrue(membership_requestor.is_member_of_community_with_name(space.name))
        self.assertFalse(membership_requestor.is_membership_requestor_of_community_with_name(space.name))

        self.assertNotification(
            membership_requestor.notifications.get(),
            type=Notification.COMMUNITY_MEMBERSHIP_APPROVED,
            user=membership_requestor,
            space=returned_space,
        )

        self.assertNotification(
            space_creator.notifications.get(),
            type=Notification.COMMUNITY_MEMBERSHIP_APPROVED,
            user=membership_requestor,
            space=returned_space,
        )

    def test_revoke_membership_denied_for_non_staff_members(self):
        membership_requestor = make_user()
        space_creator = make_user()
        other_user = make_user()

        space = make_community(creator=space_creator)
        membership_requestor.request_membership_to_community_with_name(space.name)

        with self.assertRaises(PermissionDenied):
            other_user.revoke_membership_request_to_community_for_username(membership_requestor.username, space.name)

        with self.assertRaises(PermissionDenied):
            membership_requestor.revoke_membership_request_to_community_for_username(
                membership_requestor.username, space.name
            )

    def test_revoke_membership_request_to_community_for_username(self):
        membership_requestor = make_user()
        space_creator = make_user()

        space = make_community(creator=space_creator)
        membership_requestor.request_membership_to_community_with_name(space.name)

        # precondition
        self.assertTrue(membership_requestor.is_membership_requestor_of_community_with_name(space.name))

        returned_space = space_creator.revoke_membership_request_to_community_for_username(
            membership_requestor.username, space.name
        )

        # postcondition
        self.assertFalse(membership_requestor.is_member_of_community_with_name(space.name))
        self.assertFalse(membership_requestor.is_membership_requestor_of_community_with_name(space.name))

        self.assertFalse(membership_requestor.notifications.exists())
        self.assertFalse(space_creator.notifications.exists())
