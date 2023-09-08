from enum import Enum
import json

from django.utils.translation import gettext_lazy as _
from django.db.models import TextChoices
from strawberry_django_plus import gql
from django.contrib.gis import geos


@gql.enum
class ReactionType(TextChoices):
    HEART = ("HEART",)


@gql.enum
class VisibilityType(TextChoices):
    MEMBERS = ("MEMBERS",)
    PUBLIC = ("PUBLIC",)


@gql.enum
class NeedUpdateType(TextChoices):
    NO = ("NO",)
    RECOMMENDED = ("RECOMMENDED",)
    MANDATORY = ("MANDATORY",)


@gql.enum
class FeatureToggleType(TextChoices):
    OFF = ("OFF",)
    PREVIEW = ("PREVIEW",)
    PRODUCTION = ("PRODUCTION",)
    MAINTENANCE = ("MAINTENANCE",)


# Helper class for the result of parsing GeoJSON
class GeolocationFeature:
    id: str
    name: str
    geometry: geos.GEOSGeometry

    def __init__(self, id=None, name=None, geometry=None):
        self.id = id
        self.name = name
        self.geometry = geometry

    @staticmethod
    def from_geojson(feature):
        if not feature:
            return None
        return GeolocationFeature(
            id=feature["properties"]["place_id"],
            name=feature["properties"]["formatted"],
            geometry=geos.GEOSGeometry(json.dumps(feature["geometry"])),
        )
