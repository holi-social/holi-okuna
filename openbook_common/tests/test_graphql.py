import logging

import pytest
from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.management import call_command
from django.test import AsyncClient

from openbook.graphql_schema import schema
from openbook_common.enums import FeatureToggleType, NeedUpdateType
from openbook_common.models import AppVersion, FeatureToggle
from openbook_common.tests.helpers import (
    check_app_version,
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
class TestCommons:
    def test_feature_toggles(self):
        feature_toggles = [
            FeatureToggle.objects.create(name="TOGGLE_1_PRODUCTION", status=FeatureToggleType.PRODUCTION),
            FeatureToggle.objects.create(name="TOGGLE_2_PRODUCTION", status=FeatureToggleType.PRODUCTION),
            FeatureToggle.objects.create(name="TOGGLE_3_OFF", status=FeatureToggleType.OFF),
            FeatureToggle.objects.create(name="TOGGLE_4_PREVIEW", status=FeatureToggleType.PREVIEW),
            FeatureToggle.objects.create(name="TOGGLE_5_MAINTENANCE", status=FeatureToggleType.MAINTENANCE),
        ]

        response = async_to_sync(schema.execute)(
            f"""
            query {{
                featureToggles {{
                    id
                    name
                    status
                }}
            }}
            """,
        )
        assert response.errors is None
        assert response.data is not None
        assert len(response.data["featureToggles"]) == len(feature_toggles)
        assert response.data["featureToggles"][0]["id"] == str(feature_toggles[0].id)
        assert response.data["featureToggles"][0]["name"] == feature_toggles[0].name
        assert response.data["featureToggles"][0]["status"] == feature_toggles[0].status

    def test_check_app_version(self):
        app_version = AppVersion.objects.create(version="2023.5.1000", need_update=NeedUpdateType.MANDATORY)
        app_version_2 = AppVersion.objects.create(
            version="2023.5.1000", build_number="1000", need_update=NeedUpdateType.RECOMMENDED
        )

        # Check success with existing build_number
        response = check_app_version(version="2023.5.1000", build_number="1000")
        assert response.errors is None
        assert response.data is not None
        assert response.data["checkAppVersion"]["needUpdate"] == app_version_2.need_update
        assert response.data["checkAppVersion"]["appStoreUrl"] == settings.APPLE_APP_STORE_DEFAULT_URL
        assert response.data["checkAppVersion"]["playStoreUrl"] == settings.GOOGLE_PLAY_STORE_DEFAULT_URL

        # Check success with not existing build_number
        response = check_app_version(version="2023.5.1000", build_number="1001")
        assert response.errors is None
        assert response.data is not None
        assert response.data["checkAppVersion"]["needUpdate"] == app_version.need_update
        assert response.data["checkAppVersion"]["appStoreUrl"] == settings.APPLE_APP_STORE_DEFAULT_URL
        assert response.data["checkAppVersion"]["playStoreUrl"] == settings.GOOGLE_PLAY_STORE_DEFAULT_URL

        # Check error version not found
        response = check_app_version(version="2023.5.1234", build_number="1000")
        assert response.errors is None
        assert response.data is not None
        assert response.data["checkAppVersion"]["needUpdate"] == NeedUpdateType.NO
