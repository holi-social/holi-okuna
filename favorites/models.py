import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import TextChoices, Model

from openbook_auth.models import User
from openbook_common.models import ModelWithUUID
from openbook_communities.models import Task


class FavoritableType(TextChoices):
    INSIGHT = "insight"
    EXTERNAL_VOLUNTEERING_OPPORTUNITY = "externalvolunteeringopportunity"
    TASK = "task"


class ExternalVolunteeringOpportunity(Model):
    external_id = models.CharField(primary_key=True, default="missing_external_id", editable=False)

    @staticmethod
    def cleanup_unreferenced(external_id: str):
        if not UserFavorite.objects.filter(favoritable_id=external_id).exists():
            ExternalVolunteeringOpportunity.objects.filter(external_id=external_id).delete()


class UserFavorite(ModelWithUUID):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    favoritable_id = models.CharField()
    favoritable_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    favoritable = GenericForeignKey("favoritable_type", "favoritable_id")
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def favorite(
        user: User,
        favoritable_type: FavoritableType,
        favoritable_id: str | uuid.UUID,
    ):
        favoritable = ContentType.objects.get(model=favoritable_type.value)
        if not UserFavorite.objects.filter(
            user=user, favoritable_id=favoritable_id, favoritable_type=favoritable
        ).exists():
            if FavoritableType.TASK == favoritable_type:
                task = Task.objects.filter(id=favoritable_id).filter(Task.is_visible_query(user)).first()
                if not task:
                    raise ObjectDoesNotExist()

            if FavoritableType.EXTERNAL_VOLUNTEERING_OPPORTUNITY == favoritable_type:
                if not ExternalVolunteeringOpportunity.objects.filter(external_id=favoritable_id).exists():
                    ExternalVolunteeringOpportunity.objects.create(external_id=favoritable_id)

            UserFavorite.objects.create(user=user, favoritable_id=favoritable_id, favoritable_type=favoritable)

    @staticmethod
    def unfavorite(
        user: User,
        favoritable_type: FavoritableType,
        favoritable_id: str | uuid.UUID,
    ):
        favoritable = ContentType.objects.get(model=favoritable_type.value)

        UserFavorite.objects.filter(user=user, favoritable_id=favoritable_id, favoritable_type=favoritable).delete()

        if FavoritableType.EXTERNAL_VOLUNTEERING_OPPORTUNITY == favoritable_type:
            ExternalVolunteeringOpportunity.cleanup_unreferenced(favoritable_id)

    @classmethod
    def delete_multiple_favorites_of_user(cls, favoritable_ids: list[str], user: User):
        cls.objects.filter(favoritable_id__in=favoritable_ids, user=user).delete()
