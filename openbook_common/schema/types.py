import json
from typing import Generic, List, Optional, TypeVar, Callable

import strawberry
import strawberry_django
import structlog
from asgiref.sync import sync_to_async
from django.contrib.gis import geos
from django.db.models import QuerySet

from openbook_common.models import AppVersion as AppVersionModel
from openbook_common.models import FeatureToggle as FeatureToggleModel
from openbook_common.types import GeolocationFeature

logger = structlog.get_logger(__name__)

T = TypeVar("T")


GeoJSON = strawberry.scalar(
    GeolocationFeature,
    name="GeoJSON",
    description="GeoJSON describing the geometry feature of a geolocation",
    serialize=lambda value: json.loads(
        value.geometry.geojson
    ),  # This is asymmetrical as we do not store all feature data
    parse_value=lambda value: GeolocationFeature.from_geojson(value),
)

# Separate type for GeoJSON input to be used by the GeoFeatureModelSerializer
GeoJSONInput = strawberry.scalar(
    object,
    name="GeoJSONInput",
    description="GeoJSON input describing the geometry feature of a geolocation",
    serialize=lambda value: value,
    parse_value=lambda value: value,
)


@strawberry.input
class GeolocationPointInput:
    latitude: float
    longitude: float

    @staticmethod
    def to_point(geolocation_input):
        if geolocation_input is None:
            return None

        longitude = float(geolocation_input.get("longitude"))
        latitude = float(geolocation_input.get("latitude"))
        return geos.Point(longitude, latitude, srid=4326)


@strawberry.type
class Result:
    success: bool


@strawberry.type
class GeolocationPoint:
    longitude: float
    latitude: float

    @staticmethod
    def from_point(point):
        if not point:
            return None

        return GeolocationPoint(longitude=point.x, latitude=point.y)


@strawberry_django.type(AppVersionModel)
class AppVersionResponse:
    need_update: strawberry.auto
    app_store_url: str = strawberry_django.field(
        field_name="app_store_url", default=AppVersionModel._meta.get_field("app_store_url").get_default()
    )
    play_store_url: str = strawberry_django.field(
        field_name="play_store_url", default=AppVersionModel._meta.get_field("app_store_url").get_default()
    )


@strawberry_django.type(FeatureToggleModel)
class FeatureToggle:
    id: strawberry.auto
    name: strawberry.auto
    status: strawberry.auto


@strawberry.type
class Paged(Generic[T]):
    data: List[Optional[T]] = strawberry_django.field(description="The list of items in this pagination window.")
    total_results: int = strawberry_django.field(description="Total number of items in the filtered dataset.")

    @staticmethod
    def of(query: QuerySet, offset: int, limit: int):
        return Paged(data=query[offset : offset + limit], total_results=query.count())

    @staticmethod
    async def aof(query: QuerySet, offset: int, limit: int):
        total_results = await query.acount()
        return sync_to_async(Paged)(data=query[offset : offset + limit], total_results=total_results)

    def __init__(self, data=None, total_results=0):
        if data is None:
            data = []
        self.data = data
        self.total_results = max(total_results, len(data))
