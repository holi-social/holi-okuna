import uuid

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from openbook_common.tests.assertions import TestAssertionsMixin
from openbook_common.tests.helpers import make_user, make_community, make_fake_post_text, make_fake_post_title
from openbook_notifications.models import Notification
from openbook_posts.models import PostComment


class UserModelTest(TestAssertionsMixin, TestCase):
    fixtures = ["openbook_circles/fixtures/circles.json", "openbook_moderation/fixtures/moderation_categories.json"]

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

    def test_delete_comment_with_id_success(self):
        posting_user = make_user()
        comment_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_public_post(
            text=post_text,
            title=post_title,
        )
        comment = post.comment(text=f"comment text", commenter=comment_user)
        comment2 = post.comment(text=f"comment text 2", commenter=comment_user)
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

        post = posting_user.create_public_post(
            text=post_text,
            title=post_title,
        )
        comment = post.comment(text=f"comment text", commenter=comment_user)
        post.comment(text=f"comment text 2", commenter=comment_user)
        self.assertEqual(post.comments.count(), 2)

        with self.assertRaises(PostComment.DoesNotExist):
            comment_user.delete_comment_with_id(uuid.uuid4())

        self.assertEqual(post.comments.count(), 2)
        self.assertIn(comment.id, post.comments.values_list("id", flat=True))

    def test_delete_comment_with_id_error_different_user(self):
        posting_user = make_user()
        comment_user = make_user()
        other_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_public_post(
            text=post_text,
            title=post_title,
        )
        comment = post.comment(text=f"comment text", commenter=comment_user)
        post.comment(text=f"comment text 2", commenter=other_user)
        self.assertEqual(post.comments.count(), 2)

        with self.assertRaises(ValidationError):
            other_user.delete_comment_with_id(comment.id)

        self.assertEqual(post.comments.count(), 2)
        self.assertIn(comment.id, post.comments.values_list("id", flat=True))
