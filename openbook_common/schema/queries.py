from typing import List

import strawberry
import strawberry_django
import structlog
from django.db.models import Q

from openbook_common.models import AppVersion as AppVersionModel
from openbook_common.models import FeatureToggle as FeatureToggleModel
from openbook_common.schema.types import AppVersionResponse, FeatureToggle

logger = structlog.get_logger(__name__)


@strawberry.type
class Query:
    @strawberry_django.field
    def check_app_version(self, version: str, build_number: str) -> AppVersionResponse:
        app_version = (
            AppVersionModel.objects.filter(
                Q(version=version), Q(build_number=build_number) | Q(build_number__isnull=True)
            )
            .order_by("build_number")
            .first()
        )
        if app_version:
            return app_version

        logger.info(f"App version {version} not found. Creating a new App Version.")
        return AppVersionModel.objects.create(version=version)

    @strawberry_django.field
    async def feature_toggles(self) -> List[FeatureToggle]:
        return FeatureToggleModel.objects.all()
