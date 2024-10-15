import logging

import pytest
from django.conf import settings
from django.test import AsyncClient

from openbook_common.enums import NeedUpdateType
from openbook_common.models import AppVersion
from openbook_common.tests.helpers import (
    check_app_version,
)

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def client():
    return AsyncClient()


@pytest.mark.django_db
class TestCommons:
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
