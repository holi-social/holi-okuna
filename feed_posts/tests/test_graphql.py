import logging

import pytest
import pytz
from django.contrib.auth.models import AnonymousUser
from django.test import AsyncClient, TestCase
from faker import Faker

from feed_posts.enums import VisibilityLevel
from feed_posts.tests.helpers import create_feed_post
from openbook import settings
from openbook_common.tests.helpers import (
    make_user,
    make_topic,
    make_feed_post_category,
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
        cls.public_feed_post_input_data = {
            "title": fake.text(max_nb_chars=settings.FEED_POST_TITLE_MAX_LENGTH),
            "description": fake.text(max_nb_chars=settings.FEED_POST_DESCRIPTION_MAX_LENGTH),
            "visibility": VisibilityLevel.PUBLIC,
            "categoryId": str(make_feed_post_category().id),
            "topicIds": [str(make_topic().id) for _ in range(6)],
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
