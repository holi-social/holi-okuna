from django.contrib.gis.geos import Point
from strawberry_django_plus import gql


@gql.input
class GeolocationInput:
    latitude: float
    longitude: float

    @staticmethod
    def to_point(geolocation_input):
        if geolocation_input is None:
            return None

        longitude = float(geolocation_input.get("longitude"))
        latitude = float(geolocation_input.get("latitude"))
        return Point(longitude, latitude, srid=4326)
