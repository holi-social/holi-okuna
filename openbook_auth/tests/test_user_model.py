import uuid

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from openbook.graphql_types import VisibilityType
from openbook_circles.models import Circle
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

    def test_create_community_encircled_post_success(self):
        space_creator = make_user()
        space = make_community(creator=space_creator)

        post_private_text = make_fake_post_text()
        post_private_title = make_fake_post_title()
        world_circle_id = Circle.get_world_circle_id()

        post_private = space_creator.create_community_encircled_post(
            text=post_private_text,
            title=post_private_title,
            space_id=space.id,
            visibility=VisibilityType.MEMBERS.value,
        )
        self.assertEqual(space.posts.count(), 1)
        self.assertEqual(post_private.community.id, space.id)
        self.assertEqual(post_private.text, post_private_text)
        self.assertEqual(post_private.title, post_private_title)
        self.assertNotIn(world_circle_id, post_private.circles.values_list("id", flat=True))

        post_public_text = make_fake_post_text()
        post_public_title = make_fake_post_title()
        post_public = space_creator.create_community_encircled_post(
            text=post_public_text, title=post_public_title, space_id=space.id, visibility=VisibilityType.PUBLIC.value
        )

        self.assertEqual(space.posts.count(), 2)
        self.assertEqual(post_public.community.id, space.id)
        self.assertEqual(post_public.text, post_public_text)
        self.assertEqual(post_public.title, post_public_title)
        self.assertIn(world_circle_id, post_public.circles.values_list("id", flat=True))

    def test_create_community_encircled_post_member_user_can_create_only_public_post(self):
        space_creator = make_user()
        member_user = make_user()
        space = make_community(creator=space_creator)
        space.add_member(member_user)

        post_public_text = make_fake_post_text()
        post_public_title = make_fake_post_title()
        world_circle_id = Circle.get_world_circle_id()

        public_post = member_user.create_community_encircled_post(
            text=post_public_text, title=post_public_title, space_id=space.id, visibility=VisibilityType.PUBLIC.value
        )
        self.assertEqual(space.posts.count(), 1)
        self.assertEqual(public_post.community.id, space.id)
        self.assertEqual(public_post.text, post_public_text)
        self.assertEqual(public_post.title, post_public_title)
        self.assertIn(world_circle_id, public_post.circles.values_list("id", flat=True))

        post_private_text = make_fake_post_text()
        post_private_title = make_fake_post_title()

        with self.assertRaises(ValidationError):
            member_user.create_community_encircled_post(
                text=post_private_text,
                title=post_private_title,
                space_id=space.id,
                visibility=VisibilityType.MEMBERS.value,
            )
        self.assertEqual(space.posts.count(), 1)

    def test_create_community_encircled_post_error_user_not_member(self):
        space_creator = make_user()
        not_member_user = make_user()
        space = make_community(creator=space_creator)

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        with self.assertRaises(ValidationError):
            _ = not_member_user.create_community_encircled_post(
                text=post_text, title=post_title, space_id=space.id, visibility=VisibilityType.PUBLIC.value
            )

        self.assertEqual(space.posts.count(), 0)
