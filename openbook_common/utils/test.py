import re
import uuid

_uuid_pattern = re.compile("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def is_uuid(string: str):
    return _uuid_pattern.match(string)


def uuid_id_parser(obj):
    """
    This function can be used to parse JSON id-fields that are UUID strings into UUID objects.
    Fields with other names are not recognized. id's that don't match the UUID pattern are ignored as well.
    Use it like this: json.loads(json_str, object_hook=uuid_id_parser)
    """
    if "id" in obj:
        id_str = str(obj["id"])
        if is_uuid(id_str):
            uuid_obj = uuid.UUID(id_str)
            obj["id"] = uuid_obj
    return obj
