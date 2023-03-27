from strawberry_django_plus import gql


@gql.type
class Geolocation:
    longitude: float
    latitude: float

    @staticmethod
    def from_point(point):
        if not point:
            return None

        return Geolocation(longitude=point.x, latitude=point.y)
