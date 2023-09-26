import json

from django.contrib.gis import geos


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
