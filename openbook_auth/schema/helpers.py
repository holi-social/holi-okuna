from django.db.models import Case, When

from openbook_auth.models import User
from openbook_common.schema.types import Paged
from openbook_common.utils.model_loaders import get_connection_model


def get_ordered_user_connections(circle_id, offset, limit):
    Connection = get_connection_model()
    all_connections = Connection.objects.filter(
        circles__id__isnull=False, target_connection__circles__id=circle_id
    ).order_by("-created")

    connections_ids = list(all_connections.values_list("user_id", flat=True))

    preserved_order = Case(*[When(id=pk, then=pos) for pos, pk in enumerate(connections_ids)])

    user_connections = User.objects.select_related("profile").filter(id__in=connections_ids).order_by(preserved_order)

    return Paged.of(user_connections, offset, limit)
