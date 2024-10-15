import strawberry
import strawberry_django
import structlog
from django.db.models import Q

from openbook_common.models import AppVersion as AppVersionModel
from openbook_common.schema.types import AppVersionResponse
from openbook_common.serializers import AppVersionSerializer

logger = structlog.get_logger(__name__)


@strawberry.type
class Query:
    @strawberry_django.field()
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

        serializer = AppVersionSerializer(data={"version": version, "build_number": build_number})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        logger.info(f"App version {version} not found. Creating a new App Version.")
        return AppVersionModel.objects.create(version=data["version"], build_number=data["build_number"])
