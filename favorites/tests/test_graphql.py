import logging
from unittest import TestCase

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import AsyncClient
from django.utils import timezone

import favorites.models
from favorites.schema.types import FavoritableType
from openbook_common.tests.helpers import (
    assert_is_unauthorized,
    make_user,
    simple_jpeg_bytes,
)
from openbook_common.utils.model_loaders import get_insight_model
from openbook_communities.models import Community as CommunityModel, Task as TaskModel
from openbook_common.enums import VisibilityType

from .helpers import favorite, unfavorite, query_favorites

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def client():
    return AsyncClient()


@pytest.mark.django_db
class TestFavoriteInsights(TestCase):
    def setUp(self):
        self.user = make_user()
        self.insight_author = make_user()
        self.insight_model = get_insight_model()
        self.insight = self.insight_model.objects.create(
            creator=self.insight_author,
            title="Test Insight",
            header_image=SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes),
            date_published=timezone.now(),
        )

    def test_cannot_favorite_insight_if_anonymous(self):
        response = favorite(AnonymousUser, self.insight.id, FavoritableType.INSIGHT.name)

        assert_is_unauthorized(response)

    def test_cannot_unfavorite_insight_if_anonymous(self):
        response = unfavorite(AnonymousUser, self.insight.id, FavoritableType.INSIGHT.name)

        assert_is_unauthorized(response)

    def test_can_favorite_insight_if_authenticated(self):
        response = favorite(self.user, self.insight.id, FavoritableType.INSIGHT.name)

        assert response.data["favoriteV2"]["success"]
        assert favorites.models.UserFavorite.objects.filter(user=self.user, favoritable_id=self.insight.id).exists()

        favorites_response = query_favorites(self.user)

        assert len(favorites_response.data["favorites"]["data"]) == 1
        assert favorites_response.data["favorites"]["data"][0]["favoritableId"] == str(self.insight.id)
        assert favorites_response.data["favorites"]["data"][0]["favoritable"]["title"] == self.insight.title

    def test_can_unfavorite_insight_if_authenticated(self):
        favorite(self.user, self.insight.id, FavoritableType.INSIGHT.name)
        assert favorites.models.UserFavorite.objects.filter(user=self.user, favoritable_id=self.insight.id).exists()

        response = unfavorite(self.user, self.insight.id, FavoritableType.INSIGHT.name)
        assert response.data["unfavoriteV2"]["success"]

        favorites_response = query_favorites(self.user)
        assert len(favorites_response.data["favorites"]["data"]) == 0


@pytest.mark.django_db
class TestFavoriteExternalVolunteeringOpportunities(TestCase):
    def setUp(self):
        self.user = make_user()
        self.typesense_vo_id = "volunteering_104392"

    def test_cannot_favorite_external_volunteering_opportunity_anonymously(self):
        response = favorite(
            AnonymousUser, self.typesense_vo_id, FavoritableType.EXTERNAL_VOLUNTEERING_OPPORTUNITY.name
        )

        assert_is_unauthorized(response)

    def test_cannot_unfavorite_external_volunteering_opportunity_anonymously(self):
        response = unfavorite(
            AnonymousUser, self.typesense_vo_id, FavoritableType.EXTERNAL_VOLUNTEERING_OPPORTUNITY.name
        )

        assert_is_unauthorized(response)

    def test_can_favorite_external_volunteering_opportunity(self):
        response = favorite(self.user, self.typesense_vo_id, FavoritableType.EXTERNAL_VOLUNTEERING_OPPORTUNITY.name)

        assert response.data["favoriteV2"]["success"]

        assert favorites.models.ExternalVolunteeringOpportunity.objects.filter(
            external_id=self.typesense_vo_id
        ).exists()
        assert favorites.models.UserFavorite.objects.filter(favoritable_id=self.typesense_vo_id).exists()

        favorites_response = query_favorites(self.user)

        assert len(favorites_response.data["favorites"]["data"]) == 1
        assert favorites_response.data["favorites"]["data"][0]["favoritableId"] == str(self.typesense_vo_id)
        assert favorites_response.data["favorites"]["data"][0]["favoritable"]["externalId"] == self.typesense_vo_id

    def test_can_unfavorite_external_volunteering_opportunity(self):
        favorite(self.user, self.typesense_vo_id, FavoritableType.EXTERNAL_VOLUNTEERING_OPPORTUNITY.name)
        assert favorites.models.UserFavorite.objects.filter(favoritable_id=self.typesense_vo_id).exists()

        response = unfavorite(self.user, self.typesense_vo_id, FavoritableType.EXTERNAL_VOLUNTEERING_OPPORTUNITY.name)
        assert response.data["unfavoriteV2"]["success"]

        favorites_response = query_favorites(self.user)
        assert len(favorites_response.data["favorites"]["data"]) == 0

        # and also removes reference
        assert not favorites.models.ExternalVolunteeringOpportunity.objects.filter(
            external_id=self.typesense_vo_id
        ).exists()

    def test_multiple_user_favorites_for_same_external_volunteering_opportunity_keeps_its_reference_on_singular_unfavorite(
        self,
    ):
        user1 = self.user
        user2 = make_user()

        favorite(user1, self.typesense_vo_id, FavoritableType.EXTERNAL_VOLUNTEERING_OPPORTUNITY.name)
        favorite(user2, self.typesense_vo_id, FavoritableType.EXTERNAL_VOLUNTEERING_OPPORTUNITY.name)

        assert favorites.models.ExternalVolunteeringOpportunity.objects.filter(
            external_id=self.typesense_vo_id
        ).exists()

        unfavorite(user1, self.typesense_vo_id, FavoritableType.EXTERNAL_VOLUNTEERING_OPPORTUNITY.name)

        assert favorites.models.ExternalVolunteeringOpportunity.objects.filter(
            external_id=self.typesense_vo_id
        ).exists()


@pytest.mark.django_db
class TestFavoriteTasks(TestCase):
    def setUp(self):
        self.user = make_user()
        self.community_creator = make_user()
        self.community = CommunityModel.objects.create(
            title="Test Community",
            name="test-community",
            creator=self.community_creator,
        )
        self.task = TaskModel.objects.create(
            creator=self.community_creator,
            community=self.community,
            name="Test Task",
            description="Test Task Description",
            visibility=VisibilityType.PUBLIC,
            location_type=TaskModel.LocationType.REMOTE,
            regularity=TaskModel.Regularity.ONE_TIME,
            contact_email="test@example.com",
            slots_available=5,
        )

    def test_cannot_favorite_task_if_anonymous(self):
        response = favorite(AnonymousUser, self.task.id, FavoritableType.TASK.name)

        assert_is_unauthorized(response)

    def test_cannot_unfavorite_task_if_anonymous(self):
        response = unfavorite(AnonymousUser, self.task.id, FavoritableType.TASK.name)

        assert_is_unauthorized(response)

    def test_can_favorite_task_if_authenticated(self):
        response = favorite(self.user, self.task.id, FavoritableType.TASK.name)

        assert response.data["favoriteV2"]["success"]
        assert favorites.models.UserFavorite.objects.filter(user=self.user, favoritable_id=self.task.id).exists()

        favorites_response = query_favorites(self.user)

        assert len(favorites_response.data["favorites"]["data"]) == 1
        assert favorites_response.data["favorites"]["data"][0]["favoritableId"] == str(self.task.id)
        assert favorites_response.data["favorites"]["data"][0]["favoritable"]["name"] == self.task.name

    def test_can_unfavorite_task_if_authenticated(self):
        favorite(self.user, self.task.id, FavoritableType.TASK.name)
        assert favorites.models.UserFavorite.objects.filter(user=self.user, favoritable_id=self.task.id).exists()

        response = unfavorite(self.user, self.task.id, FavoritableType.TASK.name)
        assert response.data["unfavoriteV2"]["success"]

        favorites_response = query_favorites(self.user)
        assert len(favorites_response.data["favorites"]["data"]) == 0

    def test_can_favorite_own_private_task(self):
        private_task = TaskModel.objects.create(
            creator=self.user,
            community=self.community,
            name="Private Task",
            description="Private Task Description",
            visibility=VisibilityType.MEMBERS,
            location_type=TaskModel.LocationType.REMOTE,
            regularity=TaskModel.Regularity.ONE_TIME,
            contact_email="test@example.com",
            slots_available=5,
        )

        self.community.add_member(self.user)

        response = favorite(self.user, private_task.id, FavoritableType.TASK.name)

        assert response.data["favoriteV2"]["success"]
        assert favorites.models.UserFavorite.objects.filter(user=self.user, favoritable_id=private_task.id).exists()

    def test_can_favorite_private_task_as_community_member(self):
        private_task = TaskModel.objects.create(
            creator=self.community_creator,
            community=self.community,
            name="Private Task",
            description="Private Task Description",
            visibility=VisibilityType.MEMBERS,
            location_type=TaskModel.LocationType.REMOTE,
            regularity=TaskModel.Regularity.ONE_TIME,
            contact_email="test@example.com",
            slots_available=5,
        )

        self.community.add_member(self.user)

        response = favorite(self.user, private_task.id, FavoritableType.TASK.name)

        assert response.data["favoriteV2"]["success"]
        assert favorites.models.UserFavorite.objects.filter(user=self.user, favoritable_id=private_task.id).exists()

    def test_cannot_favorite_private_task_if_not_member(self):
        other_community = CommunityModel.objects.create(
            title="Other Community",
            name="other-community",
            creator=self.community_creator,
        )

        private_task = TaskModel.objects.create(
            creator=self.community_creator,
            community=other_community,
            name="Private Task",
            description="Private Task Description",
            visibility=VisibilityType.MEMBERS,
            location_type=TaskModel.LocationType.REMOTE,
            regularity=TaskModel.Regularity.ONE_TIME,
            contact_email="test@example.com",
            slots_available=5,
        )

        # user is not a member of the community

        response = favorite(self.user, private_task.id, FavoritableType.TASK.name)

        assert not response.data["favoriteV2"]["success"]

    def test_cannot_favorite_nonexistent_task(self):
        nonexistent_task_id = "00000000-0000-0000-0000-000000000000"

        response = favorite(self.user, nonexistent_task_id, FavoritableType.TASK.name)

        assert not response.data["favoriteV2"]["success"]


@pytest.mark.django_db
class TestRespondsMultipleFavoritableTypes(TestCase):
    def setUp(self):
        self.user = make_user()
        self.typesense_vo_id = "volunteering_104393"
        self.insight_author = make_user()
        self.insight_model = get_insight_model()
        self.insight = self.insight_model.objects.create(
            creator=self.insight_author,
            title="Test Insight",
            header_image=SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes),
            date_published=timezone.now(),
        )
        self.community_creator = make_user()
        self.community = CommunityModel.objects.create(
            title="Test Community",
            name="test-community",
            creator=self.community_creator,
        )
        self.task = TaskModel.objects.create(
            creator=self.community_creator,
            community=self.community,
            name="Test Task",
            description="Test Task Description",
            visibility=VisibilityType.PUBLIC,
            location_type=TaskModel.LocationType.REMOTE,
            regularity=TaskModel.Regularity.ONE_TIME,
            contact_email="test@example.com",
            slots_available=5,
        )

    def test_can_respond_multiple_content_types_together(self):
        favorite(self.user, self.insight.id, FavoritableType.INSIGHT.name)
        favorite(self.user, self.typesense_vo_id, FavoritableType.EXTERNAL_VOLUNTEERING_OPPORTUNITY.name)
        favorite(self.user, self.task.id, FavoritableType.TASK.name)

        favorites_response = query_favorites(self.user)

        assert len(favorites_response.data["favorites"]["data"]) == 3

        assert favorites_response.data["favorites"]["data"][0]["favoritable"]["name"] == self.task.name
        assert favorites_response.data["favorites"]["data"][1]["favoritable"]["externalId"] == self.typesense_vo_id
        assert favorites_response.data["favorites"]["data"][2]["favoritable"]["title"] == self.insight.title

    def test_external_volunteering_opportunity_references_are_only_stored_when_type_needs_it(self):
        favorite(self.user, self.insight.id, FavoritableType.INSIGHT.name)
        assert not favorites.models.ExternalVolunteeringOpportunity.objects.filter(
            external_id=self.insight.id
        ).exists()

        favorite(self.user, self.typesense_vo_id, FavoritableType.EXTERNAL_VOLUNTEERING_OPPORTUNITY.name)
        assert favorites.models.ExternalVolunteeringOpportunity.objects.filter(
            external_id=self.typesense_vo_id
        ).exists()
