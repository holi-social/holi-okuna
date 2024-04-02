import logging
from unittest import TestCase, mock

import pytest
from django.core.management import call_command
from django.test import AsyncClient

from comments.models import Comment, CommentReaction
from openbook_common.enums import FeatureToggleName, FeatureToggleType, ReactionType
from openbook_common.models import FeatureToggle as FeatureToggleModel
from openbook_common.tests.helpers import (
    make_fake_post_text,
    make_fake_post_title,
    make_post,
    make_post_comment,
    make_user,
)

from .helpers import add_comment, add_reaction_to_comment, delete_comment, remove_reaction_from_comment
from .post_comment_helpers import (
    delete_post_comment,
    get_post,
    react_to_post_comment,
    update_post_comment,
)

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def client():
    return AsyncClient()


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("loaddata", "openbook_moderation/fixtures/moderation_categories.json")


@pytest.mark.django_db
class TestPostComments(TestCase):
    def setup(self):
        self.notifications_toggle = FeatureToggleModel.objects.create(
            name=FeatureToggleName.NOTIFICATIONS.value, status=FeatureToggleType.PRODUCTION
        )

    def teardown(self):
        if self.notifications_toggle.id is not None:
            self.notifications_toggle.delete()

    @mock.patch("openbook_notifications.notifications.Notifications.send_post_comment_mention_notification")
    @mock.patch("openbook_notifications.notifications.Notifications.send_post_comment_author_notification")
    def test_should_mention_a_user_in_a_post_comment(
        self, mock_send_post_comment_author_notification, mock_send_post_comment_mention_notification
    ):
        posting_user = make_user()
        mentioned_user = make_user(name="Mentioned")
        commenter = make_user(name="Commenter")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)

        input_data = {
            "postId": str(post.id),
            "text": f"comment text 1 @{mentioned_user.username}",
        }

        response = update_post_comment(commenter, input_data)
        assert response.errors is None

        post_comment_data = response.data["updatePostComment"]["postComment"]
        post_comment = Comment.objects.get(id=post_comment_data["id"])

        mock_send_post_comment_mention_notification.assert_called_once_with(post_comment=post_comment)
        mock_send_post_comment_author_notification.assert_called_once_with(post_comment=post_comment)

    @mock.patch("openbook_notifications.notifications.Notifications.send_post_comment_mention_notification")
    @mock.patch("openbook_notifications.notifications.Notifications.send_post_comment_author_notification")
    def test_should_not_send_an_author_notification_if_the_commenter_is_the_author(
        self, mock_send_post_comment_author_notification, mock_send_post_comment_mention_notification
    ):
        posting_user = make_user()
        mentioned_user = make_user(name="Mentioned")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)

        input_data = {
            "postId": str(post.id),
            "text": f"comment text 1 @{mentioned_user.username}",
        }

        response = update_post_comment(posting_user, input_data)
        assert response.errors is None

        post_comment_data = response.data["updatePostComment"]["postComment"]
        post_comment = Comment.objects.get(id=post_comment_data["id"])

        mock_send_post_comment_mention_notification.assert_called_once_with(post_comment=post_comment)
        mock_send_post_comment_author_notification.assert_not_called()

    @mock.patch("openbook_notifications.notifications.Notifications.send_post_comment_mention_notification")
    @mock.patch("openbook_notifications.notifications.Notifications.send_post_comment_author_notification")
    def test_should_not_send_an_author_notification_if_the_author_is_mentioned(
        self, mock_send_post_comment_author_notification, mock_send_post_comment_mention_notification
    ):
        posting_user = make_user()
        commenter = make_user(name="Commenter")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)

        input_data = {
            "postId": str(post.id),
            "text": f"comment text 1 @{posting_user.username}",
        }

        response = update_post_comment(commenter, input_data)
        assert response.errors is None

        post_comment_data = response.data["updatePostComment"]["postComment"]
        post_comment = Comment.objects.get(id=post_comment_data["id"])

        mock_send_post_comment_mention_notification.assert_called_once_with(post_comment=post_comment)
        mock_send_post_comment_author_notification.assert_not_called()

    def test_should_fetch_comments_and_their_stats(self):
        posting_user = make_user()
        mentioned_user = make_user(name="Mentioned")
        other_user = make_user(name="Other")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)
        post.comment(text=f"comment text 1 @{posting_user.username}", commenter=other_user)
        post.comment(
            text=f"comment text 2 @{mentioned_user.username} @{posting_user.username}",
            commenter=other_user,
        )
        post.comment(
            text=f"comment text 3 @{mentioned_user.username} @{posting_user.username}",
            commenter=other_user,
        )

        post_data = get_post(post)

        assert post_data["numberOfComments"] == 3
        assert post_data["involvedUsers"]["totalResults"] == 2
        assert len(post_data["comments"]) == 3
        assert post_data["comments"][0]["text"] == f"comment text 1 @{posting_user.username}"
        assert post_data["commenters"]["totalResults"] == 1
        assert post_data["commenters"]["data"][0]["firstName"] == other_user.name

    def test_should_delete_comment(self):
        posting_user = make_user()
        comment_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)
        comment = post.comment(text="comment text", commenter=comment_user)
        reaction = comment.react(posting_user, "HEART")
        post.comment(text="comment text 2", commenter=comment_user)

        response = delete_post_comment(comment.id, comment_user)

        assert response.errors is None
        assert response.data["deletePostComment"]["success"] is True
        assert post.comments.count() == 1
        assert comment.id not in post.comments.values_list("id", flat=True)
        assert reaction.id not in CommentReaction.objects.filter(post_comment=comment).values_list("id", flat=True)

    def test_should_not_be_able_to_delete_others_comments(self):
        posting_user = make_user()
        comment_user = make_user()
        other_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)
        comment = post.comment(text="comment text", commenter=comment_user)
        reaction = comment.react(posting_user, "HEART")
        post.comment(text="comment text 2", commenter=comment_user)

        response = delete_post_comment(comment.id, other_user)
        assert response.data is None

        assert post.comments.count() == 2
        assert comment.id in post.comments.values_list("id", flat=True)
        assert reaction.id in CommentReaction.objects.filter(post_comment=comment).values_list("id", flat=True)

    def test_should_not_be_able_to_delete_a_comment_that_does_not_exist(self):
        posting_user = make_user()
        comment_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)
        comment = post.comment(text="comment text", commenter=comment_user)
        reaction = comment.react(posting_user, "HEART")
        post.comment(text="comment text 2", commenter=comment_user)

        response = delete_post_comment("00000000-0000-0000-0000-000000000000", comment_user)
        assert response.data is None

        assert post.comments.count() == 2
        assert comment.id in post.comments.values_list("id", flat=True)
        assert reaction.id in CommentReaction.objects.filter(post_comment=comment).values_list("id", flat=True)

    def test_should_be_able_to_react_to_a_comment(self):
        posting_user = make_user()
        other_user = make_user(name="Other")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)
        comment = post.comment(text="comment text", commenter=other_user)

        react_to_post_comment(comment, "SET", posting_user)
        executed = react_to_post_comment(comment, "SET", posting_user)  # setting twice is same as setting once
        updated_post_comment = executed.data["updatePostCommentReaction"]

        assert updated_post_comment["myReaction"]["HEART"] == 1
        assert updated_post_comment["reactions"]["HEART"] == 1

        post_data = get_post(post, other_user)
        assert post_data["comments"][0]["myReaction"]["HEART"] == 0
        assert post_data["comments"][0]["reactions"]["HEART"] == 1

        react_to_post_comment(comment, "REMOVE", posting_user)
        executed = react_to_post_comment(comment, "REMOVE", posting_user)  # setting twice is same as setting once
        updated_post_comment = executed.data["updatePostCommentReaction"]
        assert updated_post_comment["myReaction"]["HEART"] == 0
        assert updated_post_comment["reactions"]["HEART"] == 0


@pytest.mark.django_db
class TestAddingComments(TestCase):
    def setup(self):
        self.notifications_toggle = FeatureToggleModel.objects.create(
            name=FeatureToggleName.NOTIFICATIONS.value, status=FeatureToggleType.PRODUCTION
        )

    def teardown(self):
        if self.notifications_toggle.id is not None:
            self.notifications_toggle.delete()

    def test_should_add_a_comment(self):
        post = make_post()
        commenter = make_user(name="Commenter")

        input_data = {
            "commentableType": "POST",
            "commentableId": str(post.id),
            "text": "test approved",
        }

        response = add_comment(commenter, input_data)
        assert response.errors is None

        comment_data = response.data["comments"]["add"]
        comment = Comment.objects.get(pk=comment_data["id"])
        assert comment.commenter == commenter
        assert comment.text == "test approved"
        assert comment.commentable == post

    @mock.patch("openbook_notifications.notifications.Notifications.send_post_comment_mention_notification")
    @mock.patch("openbook_notifications.notifications.Notifications.send_post_comment_author_notification")
    def test_should_notify_mentioned_users_and_post_author(
        self, mock_send_post_comment_author_notification, mock_send_post_comment_mention_notification
    ):
        post = make_post()
        commenter = make_user(name="Commenter")
        mentioned_user = make_user(name="Mentioned")

        input_data = {
            "commentableType": "POST",
            "commentableId": str(post.id),
            "text": f"comment text 1 @{mentioned_user.username}",
        }

        response = add_comment(commenter, input_data)
        assert response.errors is None

        comment_data = response.data["comments"]["add"]
        comment = Comment.objects.get(pk=comment_data["id"])

        mock_send_post_comment_mention_notification.assert_called_once_with(post_comment=comment)
        mock_send_post_comment_author_notification.assert_called_once_with(post_comment=comment)

    @mock.patch("openbook_notifications.notifications.Notifications.send_post_comment_mention_notification")
    @mock.patch("openbook_notifications.notifications.Notifications.send_post_comment_author_notification")
    def test_should_not_notify_author_about_their_own_comments(
        self, mock_send_post_comment_author_notification, mock_send_post_comment_mention_notification
    ):
        post = make_post()
        post_author = post.creator
        mentioned_user = make_user(name="Mentioned")

        input_data = {
            "commentableType": "POST",
            "commentableId": str(post.id),
            "text": f"comment text 1 @{mentioned_user.username}",
        }

        response = add_comment(post_author, input_data)
        assert response.errors is None

        comment_data = response.data["comments"]["add"]
        comment = Comment.objects.get(pk=comment_data["id"])

        mock_send_post_comment_mention_notification.assert_called_once_with(post_comment=comment)
        mock_send_post_comment_author_notification.assert_not_called()

    @mock.patch("openbook_notifications.notifications.Notifications.send_post_comment_mention_notification")
    @mock.patch("openbook_notifications.notifications.Notifications.send_post_comment_author_notification")
    def test_should_only_notify_the_author_once_when_they_are_mentioned(
        self, mock_send_post_comment_author_notification, mock_send_post_comment_mention_notification
    ):
        post = make_post()
        post_author = post.creator
        commenter = make_user(name="Commenter")

        input_data = {
            "commentableType": "POST",
            "commentableId": str(post.id),
            "text": f"comment text 1 @{post_author.username}",
        }

        response = add_comment(commenter, input_data)
        assert response.errors is None

        comment_data = response.data["comments"]["add"]
        comment = Comment.objects.get(pk=comment_data["id"])

        mock_send_post_comment_mention_notification.assert_called_once_with(post_comment=comment)
        mock_send_post_comment_author_notification.assert_not_called()


@pytest.mark.django_db
class TestDeletingComments(TestCase):
    def setup(self):
        self.notifications_toggle = FeatureToggleModel.objects.create(
            name=FeatureToggleName.NOTIFICATIONS.value, status=FeatureToggleType.PRODUCTION
        )

    def teardown(self):
        if self.notifications_toggle.id is not None:
            self.notifications_toggle.delete()

    def test_should_delete_own_comment(self):
        comment = make_post_comment()
        commenter = comment.commenter
        comment.react(commenter, "HEART")

        response = delete_comment(commenter, comment.id)

        assert response.errors is None
        assert response.data["comments"]["delete"]["success"] is True
        assert Comment.objects.filter(pk=comment.id).exists() is False
        assert CommentReaction.objects.filter(post_comment=comment).exists() is False

    def test_should_not_be_able_to_delete_others_comments(self):
        other_user = make_user(name="Other")
        comment = make_post_comment()
        commenter = comment.commenter
        comment.react(commenter, "HEART")

        response = delete_comment(other_user, comment.id)

        assert response.data is None
        assert response.errors is not None
        assert Comment.objects.filter(pk=comment.id).exists() is True
        assert CommentReaction.objects.filter(post_comment=comment).count() == 1

    def test_should_not_be_able_to_delete_a_comment_that_does_not_exist(self):
        comment = make_post_comment()
        commenter = comment.commenter

        response = delete_comment(commenter, "00000000-0000-0000-0000-000000000000")

        assert response.data is None
        assert response.errors is not None
        assert Comment.objects.filter(pk=comment.id).exists() is True


@pytest.mark.django_db
class TestReactingToComments(TestCase):
    def setup(self):
        self.notifications_toggle = FeatureToggleModel.objects.create(
            name=FeatureToggleName.NOTIFICATIONS.value, status=FeatureToggleType.PRODUCTION
        )

    def teardown(self):
        if self.notifications_toggle.id is not None:
            self.notifications_toggle.delete()

    def test_should_be_able_to_react_to_a_comment(self):
        comment = make_post_comment()
        commenter = comment.commenter
        other_user = make_user(name="Other")

        add_reaction_to_comment(comment, other_user)
        response = add_reaction_to_comment(comment, commenter)

        assert response.errors is None
        updated_comment = response.data["comments"]["addReaction"]
        assert updated_comment["myReaction"]["HEART"] == 1
        assert updated_comment["reactions"]["HEART"] == 2

    def test_should_be_able_to_remove_a_reaction_to_a_comment(self):
        comment = make_post_comment()
        commenter = comment.commenter
        other_user = make_user(name="Other")
        comment.react(other_user, ReactionType.HEART)
        comment.react(commenter, ReactionType.HEART)

        response = remove_reaction_from_comment(comment, commenter)

        assert response.errors is None
        updated_comment = response.data["comments"]["removeReaction"]
        assert updated_comment["myReaction"]["HEART"] == 0
        assert updated_comment["reactions"]["HEART"] == 1
