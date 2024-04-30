import logging

import pytest
import pytz
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import AsyncClient, TestCase
from faker import Faker

from feed_posts.enums import VisibilityLevel
from feed_posts.tests.helpers import create_feed_post, my_posts, posts_by_user_id, post
from openbook import settings
from openbook_common.tests.helpers import (
    make_user,
    make_topic,
    make_feed_post_category,
    simple_jpeg_bytes,
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
            "image": SimpleUploadedFile(name="image_1.jpg", content=simple_jpeg_bytes),
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

    def test_can_not_query_my_posts_if_anonymous_user(self):
        first_mutation_response = create_feed_post(user=self.user, input=self.public_feed_post_input_data)
        assert first_mutation_response.errors is None

        second_mutation_response = create_feed_post(
            user=self.user, input=self.registered_users_only_feed_post_input_data
        )
        assert second_mutation_response.errors is None

        response = my_posts(user=AnonymousUser)

        assert response.errors is not None
        assert response.data is None

        assert "Unauthorized" in str(response.errors[0].message)

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

    def test_can_query_public_and_only_registered_user_feed_posts_if_authenticated_user(self):
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
