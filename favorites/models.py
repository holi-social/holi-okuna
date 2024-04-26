import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models
from django.db.models import TextChoices

from openbook_auth.models import User
from openbook_common.models import ModelWithUUID


# Attention: the referenced model will be public in the api
# as it can be favorited by users and is part of the favorite response
class FavoritableType(TextChoices):
    INSIGHT = "insight"


class UserFavorite(ModelWithUUID):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    favoritable_id = models.UUIDField()
    favoritable_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    favoritable = GenericForeignKey("favoritable_type", "favoritable_id")
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def favorite(
        user: User,
        favoritable_type: FavoritableType,
        favoritable_id: uuid.UUID,
    ):
        generic_favoritable = ContentType.objects.get(model=favoritable_type)
        if not UserFavorite.objects.filter(
            user=user, favoritable_id=favoritable_id, favoritable_type=generic_favoritable
        ).exists():
            UserFavorite.objects.create(user=user, favoritable_id=favoritable_id, favoritable_type=generic_favoritable)

    @staticmethod
    def unfavorite(
        user: User,
        favoritable_type: FavoritableType,
        favoritable_id: uuid.UUID,
    ):
        generic_favoritable = ContentType.objects.get(model=favoritable_type)
        UserFavorite.objects.filter(
            user=user, favoritable_id=favoritable_id, favoritable_type=generic_favoritable
        ).delete()
