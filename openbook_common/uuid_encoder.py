import json
from uuid import UUID

from django.core.serializers.json import DjangoJSONEncoder


class UUIDEncoder(DjangoJSONEncoder, json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, UUID):
            # if the obj is uuid, we simply return the value of uuid
            return str(obj)
        return super().default(obj)

    # pass
