import uuid

from django.test import TransactionTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from comments.models import Comment
from openbook_auth.models import User
from openbook_common.enums import VisibilityType
from openbook_common.tests.assertions import TestAssertionsMixin
from openbook_common.tests.helpers import (
    make_community,
    make_fake_post_text,
    make_fake_post_title,
    make_user,
)
from openbook_connections.tests.helpers import connect_to_user
from openbook_notifications.models import Notification


class UserModelTest(TestAssertionsMixin, TransactionTestCase):
    fixtures = ["openbook_moderation/fixtures/moderation_categories.json"]

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

        self.assert_notification(
            membership_requestor.notifications.get(),
            type=Notification.COMMUNITY_MEMBERSHIP_APPROVED,
            user=membership_requestor,
            space=returned_space,
        )

        self.assert_notification(
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

        space_creator.revoke_membership_request_to_community_for_username(membership_requestor.username, space.name)

        # postcondition
        self.assertFalse(membership_requestor.is_member_of_community_with_name(space.name))
        self.assertFalse(membership_requestor.is_membership_requestor_of_community_with_name(space.name))

        self.assertFalse(membership_requestor.notifications.exists())
        self.assertFalse(space_creator.notifications.exists())

    def test_delete_comment_with_id_success(self):
        posting_user = make_user()
        comment_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(
            is_public=True,
            text=post_text,
            title=post_title,
        )
        comment = post.comment(text="comment text", commenter=comment_user)
        comment2 = post.comment(text="comment text 2", commenter=comment_user)
        self.assertEqual(post.comments.count(), 2)

        comment_user.delete_comment_with_id(comment.id)

        self.assertEqual(post.comments.count(), 1)
        self.assertNotIn(comment.id, post.comments.values_list("id", flat=True))
        self.assertIn(comment2.id, post.comments.values_list("id", flat=True))

    def test_delete_comment_with_id_error_wrong_id(self):
        posting_user = make_user()
        comment_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(
            is_public=True,
            text=post_text,
            title=post_title,
        )
        comment = post.comment(text="comment text", commenter=comment_user)
        post.comment(text="comment text 2", commenter=comment_user)
        self.assertEqual(post.comments.count(), 2)

        with self.assertRaises(Comment.DoesNotExist):
            comment_user.delete_comment_with_id(uuid.uuid4())

        self.assertEqual(post.comments.count(), 2)
        self.assertIn(comment.id, post.comments.values_list("id", flat=True))

    def test_delete_comment_with_id_error_different_user(self):
        posting_user = make_user()
        comment_user = make_user()
        other_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(
            is_public=True,
            text=post_text,
            title=post_title,
        )
        comment = post.comment(text="comment text", commenter=comment_user)
        post.comment(text="comment text 2", commenter=other_user)
        self.assertEqual(post.comments.count(), 2)

        with self.assertRaises(ValidationError):
            other_user.delete_comment_with_id(comment.id)

        self.assertEqual(post.comments.count(), 2)
        self.assertIn(comment.id, post.comments.values_list("id", flat=True))

    def test_create_community_encircled_post_success(self):
        space_creator = make_user()
        space = make_community(creator=space_creator)

        post_private_text = make_fake_post_text()
        post_private_title = make_fake_post_title()

        post_private = space_creator.create_community_post(
            text=post_private_text,
            title=post_private_title,
            space_id=space.id,
            visibility=VisibilityType.MEMBERS.value,
        )
        self.assertEqual(space.posts.count(), 1)
        self.assertEqual(post_private.community.id, space.id)
        self.assertEqual(post_private.text, post_private_text)
        self.assertEqual(post_private.title, post_private_title)
        self.assertFalse(post_private.is_public)

        post_public_text = make_fake_post_text()
        post_public_title = make_fake_post_title()
        post_public = space_creator.create_community_post(
            text=post_public_text, title=post_public_title, space_id=space.id, visibility=VisibilityType.PUBLIC.value
        )

        self.assertEqual(space.posts.count(), 2)
        self.assertEqual(post_public.community.id, space.id)
        self.assertEqual(post_public.text, post_public_text)
        self.assertEqual(post_public.title, post_public_title)
        self.assertTrue(post_public.is_public)

    def test_create_community_encircled_post_member_user_can_create_only_private_post(self):
        space_creator = make_user()
        member_user = make_user()
        space = make_community(creator=space_creator)
        space.add_member(member_user)

        post_private_text = make_fake_post_text()
        post_private_title = make_fake_post_title()

        private_post = member_user.create_community_post(
            text=post_private_text,
            title=post_private_title,
            space_id=space.id,
            visibility=VisibilityType.MEMBERS.value,
        )
        self.assertEqual(space.posts.count(), 1)
        self.assertEqual(private_post.community.id, space.id)
        self.assertEqual(private_post.text, post_private_text)
        self.assertEqual(private_post.title, post_private_title)

        post_public_text = make_fake_post_text()
        post_public_title = make_fake_post_title()

        with self.assertRaises(ValidationError):
            member_user.create_community_post(
                text=post_public_text,
                title=post_public_title,
                space_id=space.id,
                visibility=VisibilityType.PUBLIC.value,
            )
        self.assertEqual(space.posts.count(), 1)

    def test_create_community_encircled_post_error_user_not_member(self):
        space_creator = make_user()
        not_member_user = make_user()
        space = make_community(creator=space_creator)

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        with self.assertRaises(ValidationError):
            _ = not_member_user.create_community_post(
                text=post_text, title=post_title, space_id=space.id, visibility=VisibilityType.PUBLIC.value
            )

        self.assertEqual(space.posts.count(), 0)

    def test_update_tracking_consent(self):
        user = make_user()

        user.update(tracking_consent_analytics=True)
        self.assertEqual(user.tracking_consent_analytics, True)
        user.update(tracking_consent_personalization=False)
        self.assertEqual(user.tracking_consent_personalization, False)

        user.update(tracking_consent_analytics=False)
        self.assertEqual(user.tracking_consent_analytics, False)
        user.update(tracking_consent_personalization=True)
        self.assertEqual(user.tracking_consent_personalization, True)

    def test_bad_numbers_are_considered_invalid_identities(self):
        self.assertTrue(User.is_invalid_identity("fritz88"))
        self.assertTrue(User.is_invalid_identity("fritz69"))

        # good numbers are valid
        self.assertFalse(User.is_invalid_identity("fritz1"))
        self.assertFalse(User.is_invalid_identity("fritz99"))

    def test_full_connections(self):
        user1 = make_user()
        user2 = make_user()
        user3 = make_user()
        user4 = make_user()

        # Setup connections of user1:
        # Full connection to user2
        connect_to_user(user1, user2)
        connect_to_user(user2, user1)
        # One-sided connections to user3 and user4
        connect_to_user(user1, user3)
        connect_to_user(user4, user1)

        # Assert that connections were set up correctly
        assert user1.is_fully_connected_with_user_with_id(user2) is True
        assert user1.is_fully_connected_with_user_with_id(user3) is False
        assert user1.is_fully_connected_with_user_with_id(user4) is False

        # Check full_connections
        connections = user1.full_connections().all()
        assert len(connections) == 1
        assert connections[0].user_id == user2.id

    def test_connected_users(self):
        user1 = make_user()
        user2 = make_user()

        # Setup full connection to user2
        connect_to_user(user1, user2)
        connect_to_user(user2, user1)

        # Assert that connection was set up correctly
        assert user1.is_fully_connected_with_user_with_id(user2) is True

        users = user1.connected_users()
        assert len(users) == 1
        assert users[0].id == user2.id
