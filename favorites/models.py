import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models

from openbook_auth.models import User
from openbook_common.models import ModelWithUUID


class UserFavorite(ModelWithUUID):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    bookmark_id = models.UUIDField()
    bookmark_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    bookmark_item = GenericForeignKey("bookmark_type", "bookmark_id")
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def bookmark(
        user: User,
        bookmark_type: str,
        bookmark_id: uuid.UUID,
    ):
        _bookmark_type = ContentType.objects.get(model=bookmark_type)
        if not UserFavorite.objects.filter(user=user, bookmark_id=bookmark_id, bookmark_type=_bookmark_type).exists():
            UserFavorite.objects.create(user=user, bookmark_id=bookmark_id, bookmark_type=_bookmark_type)

    @staticmethod
    def unbookmark(
        user: User,
        bookmark_type: str,
        bookmark_id: uuid.UUID,
    ):
        _bookmark_type = ContentType.objects.get(model=bookmark_type)
        UserFavorite.objects.filter(user=user, bookmark_id=bookmark_id, bookmark_type=_bookmark_type).delete()
