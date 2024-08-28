import json
from enum import Enum

import strawberry
from django.contrib.gis import geos
from django.db.models import TextChoices


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


class ReactableType(Enum):
    QUOTE = "quote"
    RECOMMENDATION = "recommendation"
    INITIATIVE = "initiative"
    FEED_POST = "feed_post"


@strawberry.enum
class LanguageCode(TextChoices):
    ARABIC = ("ar",)
    AZERBAIJANI = ("az",)
    BULGARIAN = ("bg",)
    BENGALI = ("bn",)
    CATALAN = ("ca",)
    CZECH = ("cs",)
    DANISH = ("da",)
    GERMAN = ("de",)
    GREEK = ("el",)
    ENGLISH = ("en",)
    ESPERANTO = ("eo",)
    SPANISH = ("es",)
    ESTONIAN = ("et",)
    PERSIAN = ("fa",)
    FINNISH = ("fi",)
    FRENCH = ("fr",)
    IRISH = ("ga",)
    HEBREW = ("he",)
    HINDI = ("hi",)
    HUNGARIAN = ("hu",)
    INDONESIAN = ("id",)
    ITALIAN = ("it",)
    JAPANESE = ("ja",)
    KOREAN = ("ko",)
    LITHUANIAN = ("lt",)
    LATVIAN = ("lv",)
    MALAY = ("ms",)
    NORWEGIAN_BOKMAL = ("nb",)
    DUTCH = ("nl",)
    POLISH = ("pl",)
    PORTUGUESE = ("pt",)
    ROMANIAN = ("ro",)
    RUSSIAN = ("ru",)
    SLOVAK = ("sk",)
    SLOVENIAN = ("sl",)
    ALBANIAN = ("sq",)
    SERBIAN = ("sr",)
    SWEDISH = ("sv",)
    THAI = ("th",)
    TAGALOG = ("tl",)
    TURKISH = ("tr",)
    UKRAINIAN = ("uk",)
    URDU = ("ur",)
    VIETNAMESE = ("vi",)
    CHINESE_SIMPLIFIED = ("zh",)
    CHINESE_TRADITIONAL = ("zt",)
    FICTITIOUS_LANGUAGE = ("zz",)
