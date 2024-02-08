import strawberry
import strawberry_django

from openbook_auth.schema.types import User
from openbook_connections.models import Connection as ConnectionModel


@strawberry_django.type(ConnectionModel)
class Connection:
    id: strawberry.auto
    user: User
    target_user: User
    target_connection: strawberry.auto
