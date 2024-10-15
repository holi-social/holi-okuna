import logging
from unittest import TestCase, mock
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import AsyncClient
from novu.api import EventApi

from comments.models import Comment, CommentReaction
from openbook_auth.models import UserBlock
from openbook_common.enums import ReactionType
from openbook_common.tests.helpers import (
    make_community_post,
    make_fake_post_text,
    make_fake_post_title,
    make_insight,
    make_post,
    make_space_post_comment,
    make_user,
    make_community,
)
from openbook_insights.models.discussion import Discussion
from openbook_notifications.notifications import CommentReactionNotification

from .helpers import (
    get_comment_by_id,
    add_comment,
    add_reaction_to_comment,
    delete_comment,
    get_commenters,
    get_comments,
    get_comments_with_parent_comment_id,
    get_top_comment,
    remove_reaction_from_comment,
)
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


@pytest.fixture(scope="class")
def mock_novu_api():
    with mock.patch.object(EventApi, "trigger"):
        # prevent sending novu notifications
        yield


@pytest.mark.usefixtures("mock_novu_api")
@pytest.mark.django_db
class TestPostComments(TestCase):
    @mock.patch("openbook_notifications.services.NotificationsService.send_comment_mention_notification")
    @mock.patch("openbook_notifications.services.NotificationsService.send_commentable_author_notification")
    def test_should_mention_a_user_in_a_post_comment(
        self, mock_send_commentable_author_notification, mock_send_comment_mention_notification
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

        comment_data = response.data["updatePostComment"]["postComment"]
        comment = Comment.objects.get(id=comment_data["id"])

        mock_send_comment_mention_notification.assert_called_once_with(comment=comment)
        mock_send_commentable_author_notification.assert_called_once_with(comment=comment)

    @mock.patch("openbook_notifications.services.NotificationsService.send_comment_mention_notification")
    @mock.patch("openbook_notifications.services.NotificationsService.send_commentable_author_notification")
    def test_should_not_send_an_author_notification_if_the_commenter_is_the_author(
        self, mock_send_commentable_author_notification, mock_send_comment_mention_notification
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

        comment_data = response.data["updatePostComment"]["postComment"]
        comment = Comment.objects.get(id=comment_data["id"])

        mock_send_comment_mention_notification.assert_called_once_with(comment=comment)
        mock_send_commentable_author_notification.assert_not_called()

    @mock.patch("openbook_notifications.services.NotificationsService.send_comment_mention_notification")
    @mock.patch("openbook_notifications.services.NotificationsService.send_commentable_author_notification")
    def test_should_not_send_an_author_notification_if_the_author_is_mentioned(
        self, mock_send_commentable_author_notification, mock_send_comment_mention_notification
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

        comment_data = response.data["updatePostComment"]["postComment"]
        comment = Comment.objects.get(id=comment_data["id"])

        mock_send_comment_mention_notification.assert_called_once_with(comment=comment)
        mock_send_commentable_author_notification.assert_not_called()

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
        space = make_community(creator=posting_user)
        comment_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True, community_id=space.id)
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
        space = make_community(creator=posting_user)
        comment_user = make_user()
        other_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True, community_id=space.id)
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
        space = make_community(creator=posting_user)
        comment_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True, community_id=space.id)
        comment = post.comment(text="comment text", commenter=comment_user)
        reaction = comment.react(posting_user, "HEART")
        post.comment(text="comment text 2", commenter=comment_user)

        response = delete_post_comment("00000000-0000-0000-0000-000000000000", comment_user)
        assert response.data is None

        assert post.comments.count() == 2
        assert comment.id in post.comments.values_list("id", flat=True)
        assert reaction.id in CommentReaction.objects.filter(post_comment=comment).values_list("id", flat=True)

    @patch.object(CommentReactionNotification, "send")
    def test_should_be_able_to_react_to_a_comment(self, mock_send_comment_reaction_notification):
        posting_user = make_user()
        space = make_community(creator=posting_user)
        other_user = make_user(name="Other")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True, community_id=space.id)
        comment = post.comment(text="comment text", commenter=other_user)

        react_to_post_comment(comment, "SET", posting_user)
        mock_send_comment_reaction_notification.assert_called_once()

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


@pytest.mark.usefixtures("mock_novu_api")
@pytest.mark.django_db
class TestAddingComments(TestCase):
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

        comment_data = response.data["addComment"]
        comment = Comment.objects.get(pk=comment_data["id"])
        assert comment.commenter == commenter
        assert comment.text == "test approved"
        assert comment.commentable == post

    def test_should_add_a_comment_with_parent_comment(self):
        post = make_post()
        commenter = make_user(name="Commenter")

        root_comment = Comment.create_comment("It's greeeaat!", commenter, post)

        reply = Comment.create_comment("Just ok", commenter, post, root_comment)

        assert reply.commenter == commenter
        assert reply.parent_comment.id == root_comment.id

    @mock.patch("openbook_notifications.services.NotificationsService.send_comment_mention_notification")
    @mock.patch("openbook_notifications.services.NotificationsService.send_commentable_author_notification")
    def test_should_notify_mentioned_users_and_post_author(
        self, mock_send_commentable_author_notification, mock_send_comment_mention_notification
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

        comment_data = response.data["addComment"]
        comment = Comment.objects.get(pk=comment_data["id"])

        mock_send_comment_mention_notification.assert_called_once_with(comment=comment)
        mock_send_commentable_author_notification.assert_called_once_with(comment=comment)

    @mock.patch("openbook_notifications.services.NotificationsService.send_commentable_author_notification")
    def test_should_not_notify_author_about_their_own_comments(self, mock_send_commentable_author_notification):
        post = make_post()
        post_author = post.creator

        input_data = {
            "commentableType": "POST",
            "commentableId": str(post.id),
            "text": "comment text",
        }

        response = add_comment(post_author, input_data)
        assert response.errors is None

        mock_send_commentable_author_notification.assert_not_called()

    @mock.patch("openbook_notifications.services.NotificationsService.send_comment_mention_notification")
    @mock.patch("openbook_notifications.services.NotificationsService.send_commentable_author_notification")
    def test_should_only_notify_the_author_once_when_they_are_mentioned(
        self, mock_send_commentable_author_notification, mock_send_comment_mention_notification
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

        comment_data = response.data["addComment"]
        comment = Comment.objects.get(pk=comment_data["id"])

        mock_send_comment_mention_notification.assert_called_once_with(comment=comment)
        mock_send_commentable_author_notification.assert_not_called()


@pytest.mark.usefixtures("mock_novu_api")
@pytest.mark.django_db
class TestDeletingComments(TestCase):
    def test_should_delete_own_comment(self):
        comment = make_space_post_comment()
        commenter = comment.commenter
        comment.react(commenter, "HEART")

        response = delete_comment(commenter, comment.id)

        assert response.errors is None
        assert response.data["deleteComment"]["success"] is True
        assert Comment.objects.filter(pk=comment.id).exists() is False
        assert CommentReaction.objects.filter(post_comment=comment).exists() is False

    def test_should_not_be_able_to_delete_others_comments(self):
        other_user = make_user(name="Other")
        comment = make_space_post_comment()
        commenter = comment.commenter
        comment.react(commenter, "HEART")

        response = delete_comment(other_user, comment.id)

        assert response.data is None
        assert response.errors is not None
        assert Comment.objects.filter(pk=comment.id).exists() is True
        assert CommentReaction.objects.filter(post_comment=comment).count() == 1

    def test_should_not_be_able_to_delete_others_comments_on_discussions(self):
        other_user = make_user(name="Other")
        commenter = make_user()
        insight = make_insight()
        discussion = Discussion.objects.create(insight=insight, question="Let's discuss")
        comment = Comment.create_comment(text="This is mine, hands off", commenter=commenter, commentable=discussion)

        response = delete_comment(other_user, comment.id)

        assert response.data is None
        assert response.errors is not None
        assert Comment.objects.filter(pk=comment.id).exists() is True

    def test_should_not_be_able_to_delete_a_comment_that_does_not_exist(self):
        comment = make_space_post_comment()
        commenter = comment.commenter

        response = delete_comment(commenter, "00000000-0000-0000-0000-000000000000")

        assert response.data is None
        assert response.errors is not None
        assert Comment.objects.filter(pk=comment.id).exists() is True


@pytest.mark.usefixtures("mock_novu_api")
@pytest.mark.django_db
class TestReactingToComments(TestCase):
    def test_should_be_able_to_react_to_a_comment(self):
        comment = make_space_post_comment()
        commenter = comment.commenter
        other_user = make_user(name="Other")

        add_reaction_to_comment(comment, other_user)
        response = add_reaction_to_comment(comment, commenter)

        assert response.errors is None
        updated_comment = response.data["addReactionToComment"]
        assert updated_comment["myReaction"]["HEART"] == 1
        assert updated_comment["reactions"]["HEART"] == 2

    def test_should_be_able_to_remove_a_reaction_to_a_comment(self):
        comment = make_space_post_comment()
        commenter = comment.commenter
        other_user = make_user(name="Other")
        comment.react(other_user, ReactionType.HEART)
        comment.react(commenter, ReactionType.HEART)

        response = remove_reaction_from_comment(comment, commenter)

        assert response.errors is None
        updated_comment = response.data["removeReactionFromComment"]
        assert updated_comment["myReaction"]["HEART"] == 0
        assert updated_comment["reactions"]["HEART"] == 1


@pytest.mark.usefixtures("mock_novu_api")
@pytest.mark.django_db
class TestComments(TestCase):
    def test_comment_by_id(self):
        post = make_post()
        user = make_user(name="User")

        comment = Comment.create_comment("New comment.", user, post)

        response = get_comment_by_id(comment.id, user)

        assert response.errors is None
        assert response.data["commentById"]["id"] == str(comment.id)

    def test_should_list_comments(self):
        post = make_post()
        another_post = make_post()
        commenter = make_user(name="Commenter")
        another_commenter = make_user(name="Another Commenter")

        Comment.create_comment("It's greeeaat!", commenter, post)
        Comment.create_comment("Just ok", another_commenter, post)
        Comment.create_comment("You didn't see me, right!", another_commenter, another_post)
        response = get_comments(post.id, "POST")

        assert response.errors is None
        comments_data = response.data["commentable"]["comments"]
        assert comments_data["totalResults"] == 2
        assert len(comments_data["data"]) == 2
        assert comments_data["data"][0]["text"] == "It's greeeaat!"
        assert comments_data["data"][1]["text"] == "Just ok"
        total_comments = response.data["commentable"]["totalComments"]
        assert total_comments == 2

    def test_should_list_comments_with_parent_comment_id(self):
        post = make_post()
        commenter = make_user(name="Commenter")

        root_comment = Comment.create_comment("It's greeeaat!", commenter, post)

        Comment.create_comment("Just ok", commenter, post, root_comment)

        Comment.create_comment("You didn't see me, right!", commenter, post)
        response = get_comments_with_parent_comment_id(post.id, "POST", parent_comment_id=root_comment.id)

        assert response.errors is None
        comments_data = response.data["commentable"]["comments"]
        assert comments_data["totalResults"] == 1
        assert len(comments_data["data"]) == 1
        assert comments_data["data"][0]["text"] == "Just ok"
        total_comments = response.data["commentable"]["totalComments"]
        assert total_comments == 3

    def test_should_list_replies(self):
        post = make_post()
        commenter = make_user(name="Commenter")

        root_comment = Comment.create_comment("It's greeeaat!", commenter, post)

        reply = Comment.create_comment("Just ok", commenter, post, root_comment)

        # create a non-reply comment
        Comment.create_comment("You didn't see me, right!", commenter, post)
        response = get_comments(post.id, "POST")

        assert response.errors is None
        comments_data = response.data["commentable"]["comments"]

        # total results should be all except for the reply
        assert comments_data["totalResults"] == 2
        assert len(comments_data["data"]) == 2

        # first level comments check
        assert comments_data["data"][0]["text"] == "It's greeeaat!"
        assert comments_data["data"][1]["text"] == "You didn't see me, right!"

        # second level comments check
        assert comments_data["data"][0]["totalReplies"] == 1
        assert comments_data["data"][0]["replies"][0]["id"] == str(reply.id)
        assert comments_data["data"][1]["totalReplies"] == 0

    def test_should_not_list_comments_for_private_commentables(self):
        post = make_community_post()
        non_community_member = make_user()
        Comment.create_comment("It's greeeaat!", post.creator, post)

        response = get_comments(post.id, "POST", non_community_member)

        assert response.errors is not None
        assert response.data is None

    def test_should_list_people_who_are_commenting_on_the_content(self):
        post = make_post()
        another_post = make_post()
        commenter = make_user(name="Commenter")
        last_commenter = make_user(name="Last Commenter")
        yet_another_commenter = make_user(name="Yet Another Commenter")

        Comment.create_comment("It's greeeaat!", commenter, post)
        Comment.create_comment("Just ok", last_commenter, post)
        Comment.create_comment("You didn't see me, right!", last_commenter, another_post)
        Comment.create_comment("Nor me!", yet_another_commenter, another_post)
        response = get_commenters(post.id, "POST")

        assert response.errors is None
        commenters_data = response.data["commentable"]["commenters"]
        assert commenters_data["totalResults"] == 2
        assert len(commenters_data["data"]) == 2
        self.assertCountEqual(
            ("Commenter", "Last Commenter"),
            (commenters_data["data"][0]["firstName"], commenters_data["data"][1]["firstName"]),
        )
        post_total_comments = response.data["commentable"]["totalComments"]
        assert post_total_comments == 2

    def test_should_get_the_most_interesting_comment_for_the_content(self):
        post = make_post()
        another_post = make_post()
        commenter = make_user(name="Commenter")
        last_commenter = make_user(name="Last Commenter")

        Comment.create_comment("It's greeeaat!", commenter, post)
        Comment.create_comment("Latest comment", last_commenter, post)
        Comment.create_comment("You didn't see me, right!", last_commenter, another_post)
        # For now, this is the last comment. It will evolve to be the most relevant to the user.
        response = get_top_comment(post.id, "POST")

        assert response.errors is None
        top_comment_data = response.data["commentable"]["topComment"]
        assert top_comment_data["text"] == "Latest comment"

    def test_should_not_get_the_most_interesting_comment_from_my_blocked_users(self):
        post = make_post()
        blocker = make_user(name="Blocker")
        commenter = make_user(name="Commenter")
        last_commenter = make_user(name="Last Commenter")

        Comment.create_comment("2nd latest comment", commenter, post)
        Comment.create_comment("Latest comment by a user I blocked", last_commenter, post)

        UserBlock.create_user_block(blocker.id, last_commenter.id)

        response = get_top_comment(post.id, "POST", blocker)

        assert response.errors is None
        top_comment_data = response.data["commentable"]["topComment"]
        assert top_comment_data["text"] == "2nd latest comment"
