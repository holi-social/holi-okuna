from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import NotFound


def space_member_exists(creator_id):
    from openbook_auth.models import User

    if not User.user_with_username_exists(username=creator_id):
        raise NotFound(_(f"Space member with username {creator_id} not found"))
