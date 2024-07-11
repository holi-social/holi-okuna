import logging

import pytest
import pytz
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import AsyncClient, TestCase
from faker import Faker

from feed_posts.enums import VisibilityLevel
from feed_posts.tests.helpers import (
    create_feed_post,
    my_posts,
    posts_by_user_id,
    post,
    update_feed_post,
    update_input_data,
    feed_posts,
    delete_feed_post,
    update_feed_post_reaction,
    all_posts,
)
from openbook import settings
from openbook_common.enums import ReactionType, ReactionAction, VisibilityType
from openbook_common.tests.helpers import (
    make_user,
    make_topic,
    make_feed_post_category,
    simple_jpeg_bytes,
    make_community,
)

logger = logging.getLogger(__name__)
fake = Faker()
tz = pytz.timezone("Europe/Amsterdam")


@pytest.fixture(scope="session")
def client():
    return AsyncClient()


@pytest.mark.django_db
class TestFeedPosts(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()
        cls.another_user = make_user()
        cls.yet_another_user = make_user()
        cls.space = make_community(creator=cls.user)
        cls.space.add_member(cls.yet_another_user)

        cls.public_feed_post_input_data = {
            "title": fake.text(max_nb_chars=settings.FEED_POST_TITLE_MAX_LENGTH),
            "description": fake.text(max_nb_chars=settings.FEED_POST_DESCRIPTION_MAX_LENGTH),
            "visibility": VisibilityLevel.PUBLIC,
            "categoryId": str(make_feed_post_category().id),
            "topicIds": [str(make_topic().id) for _ in range(6)],
            "image": SimpleUploadedFile(name="image_1.jpg", content=simple_jpeg_bytes),
        }

        cls.registered_users_only_feed_post_input_data = {
            "title": fake.text(max_nb_chars=settings.FEED_POST_TITLE_MAX_LENGTH),
            "description": fake.text(max_nb_chars=settings.FEED_POST_DESCRIPTION_MAX_LENGTH),
            "visibility": VisibilityLevel.REGISTERED_USERS_ONLY,
            "categoryId": str(make_feed_post_category().id),
            "topicIds": [str(make_topic().id) for _ in range(3)],
            "image": SimpleUploadedFile(name="image_2.jpg", content=simple_jpeg_bytes),
        }

        cls.another_public_feed_post_input_data = {
            "title": fake.text(max_nb_chars=settings.FEED_POST_TITLE_MAX_LENGTH),
            "description": fake.text(max_nb_chars=settings.FEED_POST_DESCRIPTION_MAX_LENGTH),
            "visibility": VisibilityLevel.PUBLIC,
            "categoryId": str(make_feed_post_category().id),
            "topicIds": [str(make_topic().id) for _ in range(6)],
            "image": SimpleUploadedFile(name="image_3.jpg", content=simple_jpeg_bytes),
        }

        cls.another_registered_users_only_feed_post_input_data = {
            "title": fake.text(max_nb_chars=settings.FEED_POST_TITLE_MAX_LENGTH),
            "description": fake.text(max_nb_chars=settings.FEED_POST_DESCRIPTION_MAX_LENGTH),
            "visibility": VisibilityLevel.REGISTERED_USERS_ONLY,
            "categoryId": str(make_feed_post_category().id),
            "topicIds": [str(make_topic().id) for _ in range(3)],
            "image": SimpleUploadedFile(name="image_4.jpg", content=simple_jpeg_bytes),
        }

        cls.feed_post_with_mentions_input_data = {
            "title": fake.text(max_nb_chars=settings.FEED_POST_TITLE_MAX_LENGTH),
            "description": f"@{cls.another_user.username} @{cls.yet_another_user.username} {fake.text(max_nb_chars=100)}",
            "visibility": VisibilityLevel.PUBLIC,
            "categoryId": str(make_feed_post_category().id),
            "topicIds": [str(make_topic().id) for _ in range(6)],
            "image": SimpleUploadedFile(name="image_1.jpg", content=simple_jpeg_bytes),
        }

        cls.another_feed_post_with_mentions_input_data = {
            "title": fake.text(max_nb_chars=settings.FEED_POST_TITLE_MAX_LENGTH),
            "description": f"@{cls.another_user.username} {fake.text(max_nb_chars=100)}",
            "visibility": VisibilityLevel.PUBLIC,
            "categoryId": str(make_feed_post_category().id),
            "topicIds": [str(make_topic().id) for _ in range(6)],
            "image": SimpleUploadedFile(name="image_1.jpg", content=simple_jpeg_bytes),
        }

        cls.public_space_post = {
            "title": fake.text(max_nb_chars=settings.POST_TITLE_MAX_LENGTH),
            "text": fake.text(max_nb_chars=settings.POST_MAX_LENGTH),
            "visibility": VisibilityType.PUBLIC.value,
        }

        cls.private_space_post = {
            "title": fake.text(max_nb_chars=settings.POST_TITLE_MAX_LENGTH),
            "text": fake.text(max_nb_chars=settings.POST_MAX_LENGTH),
            "visibility": VisibilityType.MEMBERS.value,
        }

    def test_can_not_create_feed_post_if_anonymous_user(self):
        response = create_feed_post(user=AnonymousUser, input=self.public_feed_post_input_data)

        assert response.errors is not None
        assert response.data is None

        assert "Unauthorized" in str(response.errors[0].message)

    def test_can_create_feed_post_if_registered_user(self):
        response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        data = response.data["createFeedPost"]

        assert data["title"] == self.public_feed_post_input_data["title"]
        assert data["description"] == self.public_feed_post_input_data["description"]
        assert data["visibility"] == self.public_feed_post_input_data["visibility"]
        assert data["category"]["id"] == self.public_feed_post_input_data["categoryId"]
        assert len(data["topics"]) == len(self.public_feed_post_input_data["topicIds"])
        assert data["creator"]["id"] == str(self.user.pk)
        assert data["image"]

    def test_can_query_my_posts_if_anonymous_user(self):
        first_mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        assert first_mutation_response.errors is None

        second_mutation_response = create_feed_post(
            user=self.user, input=self.registered_users_only_feed_post_input_data
        )
        assert second_mutation_response.errors is None

        response = my_posts(user=AnonymousUser)

        assert response.errors is None

        data = response.data["myPosts"]

        assert data["totalResults"] == 0

    def test_can_query_my_posts_if_authenticated_user(self):
        # first user creates 2 feed posts
        first_mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        assert first_mutation_response.errors is None

        second_mutation_response = create_feed_post(
            user=self.user, input=self.registered_users_only_feed_post_input_data
        )
        assert second_mutation_response.errors is None

        # second user creates 1 feed post
        third_mutation_response = create_feed_post(
            user=self.another_user, input=self.another_public_feed_post_input_data
        )
        assert third_mutation_response.errors is None

        #  first user queries his feed posts
        response = my_posts(user=self.user)

        data = response.data["myPosts"]

        #  first user can see only his 2 created feed posts
        assert data["totalResults"] == 2

    def test_can_query_only_public_feed_posts_by_user_if_anonymous_user(self):
        # user creates 2 public feed posts and 1 registered users only feed post
        first_mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        assert first_mutation_response.errors is None

        second_mutation_response = create_feed_post(user=self.user, input=self.another_public_feed_post_input_data)
        assert second_mutation_response.errors is None

        third_mutation_response = create_feed_post(
            user=self.user, input=self.registered_users_only_feed_post_input_data
        )
        assert third_mutation_response.errors is None

        # anonymous user queries user's feed posts
        response = posts_by_user_id(user=AnonymousUser, user_id=self.user.username)

        data = response.data["postsByUserId"]

        #  anonymous user can see only 2 public feed posts
        assert data["totalResults"] == 2

    def test_can_query_public_and_only_registered_user_feed_posts_by_user_if_authenticated_user(self):
        # user creates 2 public feed posts and 1 registered users only feed post
        first_mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        assert first_mutation_response.errors is None

        second_mutation_response = create_feed_post(user=self.user, input=self.another_public_feed_post_input_data)
        assert second_mutation_response.errors is None

        third_mutation_response = create_feed_post(
            user=self.user, input=self.registered_users_only_feed_post_input_data
        )
        assert third_mutation_response.errors is None

        # another user queries user's feed posts
        response = posts_by_user_id(user=self.another_user, user_id=self.user.username)

        data = response.data["postsByUserId"]

        # another user can see all user's public and registered user only feed posts
        assert data["totalResults"] == 3

    def test_cannot_query_registered_only_users_feed_post_if_anonymous_user(self):
        mutation_response = create_feed_post(user=self.user, input=self.registered_users_only_feed_post_input_data)
        assert mutation_response.errors is None

        post_id = mutation_response.data["createFeedPost"]["id"]

        response = post(user=AnonymousUser, id_or_slug=post_id)

        assert response.errors is not None
        assert response.data is None

        assert "You cannot query registered only users feed posts" in response.errors[0].extensions["errors"]

    def test_can_query_public_feed_post_if_anonymous_user(self):
        mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        assert mutation_response.errors is None

        post_slug = mutation_response.data["createFeedPost"]["slug"]

        response = post(user=AnonymousUser, id_or_slug=post_slug)

        data = response.data["post"]

        assert data["title"] == self.public_feed_post_input_data["title"]
        assert data["description"] == self.public_feed_post_input_data["description"]
        assert data["visibility"] == self.public_feed_post_input_data["visibility"]
        assert data["category"]["id"] == self.public_feed_post_input_data["categoryId"]
        assert len(data["topics"]) == len(self.public_feed_post_input_data["topicIds"])
        assert data["creator"]["id"] == str(self.user.pk)
        assert data["image"]

    def test_can_query_registered_only_users_feed_post_if_authenticated_user(self):
        mutation_response = create_feed_post(user=self.user, input=self.registered_users_only_feed_post_input_data)
        assert mutation_response.errors is None

        post_id = mutation_response.data["createFeedPost"]["id"]

        response = post(user=self.another_user, id_or_slug=post_id)

        data = response.data["post"]

        assert data["title"] == self.registered_users_only_feed_post_input_data["title"]
        assert data["description"] == self.registered_users_only_feed_post_input_data["description"]
        assert data["visibility"] == self.registered_users_only_feed_post_input_data["visibility"]
        assert data["category"]["id"] == self.registered_users_only_feed_post_input_data["categoryId"]
        assert len(data["topics"]) == len(self.registered_users_only_feed_post_input_data["topicIds"])
        assert data["creator"]["id"] == str(self.user.pk)
        assert data["image"]

    def test_can_query_public_feed_post_if_authenticated_user(self):
        mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        assert mutation_response.errors is None

        post_slug = mutation_response.data["createFeedPost"]["slug"]

        response = post(user=self.another_user, id_or_slug=post_slug)

        data = response.data["post"]

        assert data["title"] == self.public_feed_post_input_data["title"]
        assert data["description"] == self.public_feed_post_input_data["description"]
        assert data["visibility"] == self.public_feed_post_input_data["visibility"]
        assert data["category"]["id"] == self.public_feed_post_input_data["categoryId"]
        assert len(data["topics"]) == len(self.public_feed_post_input_data["topicIds"])
        assert data["creator"]["id"] == str(self.user.pk)
        assert data["image"]

    def test_can_not_update_feed_post_if_anonymous_user(self):
        mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        assert mutation_response.errors is None

        post_id = mutation_response.data["createFeedPost"]["id"]

        input_data = update_input_data(post_id=post_id, input_data=self.another_public_feed_post_input_data)

        response = update_feed_post(user=AnonymousUser, input=input_data)

        assert response.errors is not None
        assert response.data is None

        assert "Unauthorized" in str(response.errors[0].message)

    def test_can_not_update_feed_post_if_not_owner(self):
        mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        assert mutation_response.errors is None

        post_id = mutation_response.data["createFeedPost"]["id"]

        input_data = update_input_data(post_id=post_id, input_data=self.another_public_feed_post_input_data)

        response = update_feed_post(user=self.another_user, input=input_data)

        assert response.errors is not None
        assert response.data is None

        assert "You cannot update this feed post" in response.errors[0].extensions["errors"]

    def test_can_update_feed_post_if_owner(self):
        mutation_response = create_feed_post(user=self.user, input=self.another_public_feed_post_input_data)
        assert mutation_response.errors is None

        post_id = mutation_response.data["createFeedPost"]["id"]

        input_data = update_input_data(post_id=post_id, input_data=self.registered_users_only_feed_post_input_data)

        response = update_feed_post(user=self.user, input=input_data)

        data = response.data["updateFeedPost"]

        assert data["title"] == self.registered_users_only_feed_post_input_data["title"]
        assert data["description"] == self.registered_users_only_feed_post_input_data["description"]
        assert data["visibility"] == self.registered_users_only_feed_post_input_data["visibility"]
        assert data["category"]["id"] == self.registered_users_only_feed_post_input_data["categoryId"]
        assert len(data["topics"]) == len(self.registered_users_only_feed_post_input_data["topicIds"])
        assert data["creator"]["id"] == str(self.user.pk)
        assert data["image"]

    def test_can_query_only_public_feed_posts_if_anonymous_user(self):
        # user creates 2 public feed posts and 2 registered users only feed post
        first_mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        assert first_mutation_response.errors is None

        second_mutation_response = create_feed_post(
            user=self.user, input=self.registered_users_only_feed_post_input_data
        )
        assert second_mutation_response.errors is None

        third_mutation_response = create_feed_post(user=self.user, input=self.another_public_feed_post_input_data)
        assert third_mutation_response.errors is None

        fourth_mutation_response = create_feed_post(
            user=self.user, input=self.another_registered_users_only_feed_post_input_data
        )
        assert fourth_mutation_response.errors is None

        # anonymous user queries feed posts
        response = feed_posts(user=AnonymousUser)

        data = response.data["feedPosts"]

        #  anonymous user can see only 2 feed posts
        assert data["totalResults"] == 2

        assert data["data"][0]["visibility"] == VisibilityLevel.PUBLIC
        assert data["data"][1]["visibility"] == VisibilityLevel.PUBLIC

    def test_can_query_public_and_only_registered_user_feed_posts_if_authenticated_user(self):
        # user creates 2 public feed posts and 2 registered users only feed post
        first_mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        assert first_mutation_response.errors is None

        second_mutation_response = create_feed_post(
            user=self.user, input=self.registered_users_only_feed_post_input_data
        )
        assert second_mutation_response.errors is None

        third_mutation_response = create_feed_post(user=self.user, input=self.another_public_feed_post_input_data)
        assert third_mutation_response.errors is None

        fourth_mutation_response = create_feed_post(
            user=self.user, input=self.another_registered_users_only_feed_post_input_data
        )
        assert fourth_mutation_response.errors is None

        # another user queries feed posts
        response = feed_posts(user=self.another_user)

        data = response.data["feedPosts"]

        #  another user can see all 4 feed posts
        assert data["totalResults"] == 4

        assert data["data"][0]["visibility"] == VisibilityLevel.REGISTERED_USERS_ONLY
        assert data["data"][1]["visibility"] == VisibilityLevel.PUBLIC

    def test_can_not_delete_feed_post_if_anonymous_user(self):
        mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        assert mutation_response.errors is None

        post_id = mutation_response.data["createFeedPost"]["id"]

        response = delete_feed_post(user=AnonymousUser, post_id=post_id)

        assert response.errors is not None
        assert response.data is None

        assert "Unauthorized" in str(response.errors[0].message)

    def test_can_not_delete_feed_post_if_not_owner(self):
        mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        assert mutation_response.errors is None

        post_id = mutation_response.data["createFeedPost"]["id"]

        response = delete_feed_post(user=self.another_user, post_id=post_id)

        assert response.errors is not None
        assert response.data is None

        assert "You cannot delete this feed post" in response.errors[0].extensions["errors"]

    def test_can_delete_feed_post_if_owner(self):
        mutation_response = create_feed_post(user=self.user, input=self.another_public_feed_post_input_data)
        assert mutation_response.errors is None

        post_id = mutation_response.data["createFeedPost"]["id"]

        response = delete_feed_post(user=self.user, post_id=post_id)

        data = response.data["deleteFeedPost"]

        assert data["success"]

    def test_can_not_react_to_feed_post_if_anonymous_user(self):
        mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        assert mutation_response.errors is None

        post_id = mutation_response.data["createFeedPost"]["id"]

        response = update_feed_post_reaction(
            user=AnonymousUser,
            post_id=post_id,
            reaction_type=ReactionType.HEART,
            reaction_action=ReactionAction.SET.value,
        )

        assert response.errors is not None
        assert response.data is None

        assert "Unauthorized" in str(response.errors[0].message)

    def test_can_react_to_feed_post_if_authenticated_user(self):
        mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        assert mutation_response.errors is None

        post_id = mutation_response.data["createFeedPost"]["id"]

        response = update_feed_post_reaction(
            user=self.another_user,
            post_id=post_id,
            reaction_type=ReactionType.HEART,
            reaction_action=ReactionAction.SET.value,
        )

        data = response.data["updateFeedPostReaction"]

        assert data["myReaction"] == {"HEART": 1}
        assert data["reactions"] == {"HEART": 1}

    def test_can_remove_reaction_to_feed_post_if_authenticated_user(self):
        mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        assert mutation_response.errors is None

        post_id = mutation_response.data["createFeedPost"]["id"]

        # user reacts to the post
        update_feed_post_reaction(
            user=self.another_user,
            post_id=post_id,
            reaction_type=ReactionType.HEART,
            reaction_action=ReactionAction.SET.value,
        )

        # user removes reaction
        response = update_feed_post_reaction(
            user=self.another_user,
            post_id=post_id,
            reaction_type=ReactionType.HEART,
            reaction_action=ReactionAction.REMOVE.value,
        )

        data = response.data["updateFeedPostReaction"]

        assert data["myReaction"] == {"HEART": 0}
        assert data["reactions"] == {"HEART": 0}

    def test_can_mention_users_in_feed_post(self):
        # create feed post with 2 mentioned users
        response = create_feed_post(user=self.user, input=self.feed_post_with_mentions_input_data)
        data = response.data["createFeedPost"]

        assert len(data["mentions"]) == 2
        assert data["mentions"][0]["id"] == self.another_user.username
        assert data["mentions"][0]["fullName"] == self.another_user.profile.full_name()
        assert data["mentions"][1]["id"] == self.yet_another_user.username
        assert data["mentions"][1]["fullName"] == self.yet_another_user.profile.full_name()

    def test_can_update_mentioned_users_in_feed_post(self):
        # create feed post with 2 mentioned users
        mutation_response = create_feed_post(user=self.user, input=self.feed_post_with_mentions_input_data)
        assert mutation_response.errors is None

        mutation_data = mutation_response.data["createFeedPost"]
        assert len(mutation_data["mentions"]) == 2

        # update feed post with 1 mentioned user
        post_id = mutation_data["id"]
        input_data = update_input_data(post_id=post_id, input_data=self.another_feed_post_with_mentions_input_data)
        response = update_feed_post(user=self.user, input=input_data)
        data = response.data["updateFeedPost"]

        assert len(data["mentions"]) == 1
        assert data["mentions"][0]["id"] == self.another_user.username
        assert data["mentions"][0]["fullName"] == self.another_user.profile.full_name()

    def test_can_delete_mentioned_users_in_feed_post(self):
        # create feed post with 2 mentioned users
        mutation_response = create_feed_post(user=self.user, input=self.feed_post_with_mentions_input_data)
        assert mutation_response.errors is None

        mutation_data = mutation_response.data["createFeedPost"]
        assert len(mutation_data["mentions"]) == 2

        # update feed post with no mentioned users
        post_id = mutation_data["id"]
        input_data = update_input_data(post_id=post_id, input_data=self.public_feed_post_input_data)
        response = update_feed_post(user=self.user, input=input_data)
        data = response.data["updateFeedPost"]
        assert len(data["mentions"]) == 0

    def test_can_query_only_public_posts_if_anonymous_user(self):
        # user creates 2 public feed posts
        first_mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        assert first_mutation_response.errors is None
        first_public_feed_post = first_mutation_response.data["createFeedPost"]

        second_mutation_response = create_feed_post(
            user=self.user, input=self.registered_users_only_feed_post_input_data
        )
        assert second_mutation_response.errors is None

        # user creates 2 registered users only feed post
        third_mutation_response = create_feed_post(user=self.user, input=self.another_public_feed_post_input_data)
        assert third_mutation_response.errors is None
        second_public_feed_post = third_mutation_response.data["createFeedPost"]

        fourth_mutation_response = create_feed_post(
            user=self.user, input=self.another_registered_users_only_feed_post_input_data
        )
        assert fourth_mutation_response.errors is None

        # user create public space post
        public_space_post = self.user.create_community_post(
            space_id=self.space.id,
            title=self.public_space_post["title"],
            text=self.public_space_post["text"],
            visibility=self.public_space_post["visibility"],
        )

        # user create private space post
        self.user.create_community_post(
            space_id=self.space.id,
            title=self.private_space_post["title"],
            text=self.private_space_post["text"],
            visibility=self.private_space_post["visibility"],
        )

        # anonymous user queries all posts
        response = all_posts(user=AnonymousUser)

        data = response.data["allPosts"]

        #  anonymous user can see only 3 posts; a space post and 2 feed posts sorted by creation date
        assert data["totalResults"] == 3

        assert data["data"][0]["id"] == str(public_space_post.id)
        assert data["data"][0]["isPublic"]

        assert data["data"][1]["id"] == second_public_feed_post["id"]
        assert data["data"][1]["visibility"] == VisibilityLevel.PUBLIC

        assert data["data"][2]["id"] == first_public_feed_post["id"]
        assert data["data"][2]["visibility"] == VisibilityLevel.PUBLIC

    def test_can_query_all_feed_posts_but_only_public_space_posts_if_authenticated(self):
        # user creates 2 public feed posts
        first_mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        first_public_feed_post = first_mutation_response.data["createFeedPost"]

        second_mutation_response = create_feed_post(
            user=self.user, input=self.registered_users_only_feed_post_input_data
        )
        first_registered_users_only_feed_post = second_mutation_response.data["createFeedPost"]

        # user creates 2 registered users only feed post
        third_mutation_response = create_feed_post(user=self.user, input=self.another_public_feed_post_input_data)
        second_public_feed_post = third_mutation_response.data["createFeedPost"]

        fourth_mutation_response = create_feed_post(
            user=self.user, input=self.another_registered_users_only_feed_post_input_data
        )
        second_registered_users_only_feed_post = fourth_mutation_response.data["createFeedPost"]

        # user create public space post
        public_space_post = self.user.create_community_post(
            space_id=self.space.id,
            title=self.public_space_post["title"],
            text=self.public_space_post["text"],
            visibility=self.public_space_post["visibility"],
        )

        # user create private space post
        self.user.create_community_post(
            space_id=self.space.id,
            title=self.private_space_post["title"],
            text=self.private_space_post["text"],
            visibility=self.private_space_post["visibility"],
        )

        # authenticated user queries all posts
        response = all_posts(user=self.another_user)

        data = response.data["allPosts"]

        # authenticated user can see only 5 posts; a public space post and all feed posts sorted by creation date
        assert data["totalResults"] == 5

        assert data["data"][0]["id"] == str(public_space_post.id)
        assert data["data"][0]["isPublic"]

        assert data["data"][1]["id"] == second_registered_users_only_feed_post["id"]
        assert data["data"][1]["visibility"] == VisibilityLevel.REGISTERED_USERS_ONLY

        assert data["data"][2]["id"] == second_public_feed_post["id"]
        assert data["data"][2]["visibility"] == VisibilityLevel.PUBLIC

        assert data["data"][3]["id"] == first_registered_users_only_feed_post["id"]
        assert data["data"][3]["visibility"] == VisibilityLevel.REGISTERED_USERS_ONLY

        assert data["data"][4]["id"] == first_public_feed_post["id"]
        assert data["data"][4]["visibility"] == VisibilityLevel.PUBLIC

    def test_can_query_all_feed_posts_and_all_space_posts_if_member(self):
        # user creates 2 public feed posts
        first_mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        first_public_feed_post = first_mutation_response.data["createFeedPost"]

        second_mutation_response = create_feed_post(
            user=self.user, input=self.registered_users_only_feed_post_input_data
        )
        first_registered_users_only_feed_post = second_mutation_response.data["createFeedPost"]

        # user creates 2 registered users only feed post
        third_mutation_response = create_feed_post(user=self.user, input=self.another_public_feed_post_input_data)
        second_public_feed_post = third_mutation_response.data["createFeedPost"]

        fourth_mutation_response = create_feed_post(
            user=self.user, input=self.another_registered_users_only_feed_post_input_data
        )
        second_registered_users_only_feed_post = fourth_mutation_response.data["createFeedPost"]

        # user create public space post
        public_space_post = self.user.create_community_post(
            space_id=self.space.id,
            title=self.public_space_post["title"],
            text=self.public_space_post["text"],
            visibility=self.public_space_post["visibility"],
        )

        # user create private space post
        private_space_post = self.user.create_community_post(
            space_id=self.space.id,
            title=self.private_space_post["title"],
            text=self.private_space_post["text"],
            visibility=self.private_space_post["visibility"],
        )

        # space member queries all posts
        response = all_posts(user=self.yet_another_user)

        data = response.data["allPosts"]

        # space member can see only all posts
        assert data["totalResults"] == 6

        assert data["data"][0]["id"] == str(private_space_post.id)
        assert data["data"][1]["id"] == str(public_space_post.id)
        assert data["data"][2]["id"] == second_registered_users_only_feed_post["id"]
        assert data["data"][3]["id"] == second_public_feed_post["id"]
        assert data["data"][4]["id"] == first_registered_users_only_feed_post["id"]
        assert data["data"][5]["id"] == first_public_feed_post["id"]
