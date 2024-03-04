from enum import auto
from typing import Self

from django.contrib.gis.db import models

from openbook_common.models import ModelWithUUID
from openbook_communities.models import Community


class SpacesRelationshipType(models.TextChoices):
    PARENT_OF = auto()
    PART_OF = auto()

    @property
    def inverse(self) -> Self:
        match self:
            case SpacesRelationshipType.PART_OF:
                return SpacesRelationshipType.PARENT_OF
            case SpacesRelationshipType.PARENT_OF:
                return SpacesRelationshipType.PART_OF
            case _:
                raise NotImplementedError()


class SpacesRelationship(ModelWithUUID):
    from_space = models.ForeignKey(Community, related_name="space_relationships", on_delete=models.CASCADE)
    relationship_type: SpacesRelationshipType = models.CharField(choices=SpacesRelationshipType.choices)
    to_space = models.ForeignKey(Community, related_name="inverse_space_relationships", on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not SpacesRelationship.objects.filter(**self._inverse_relationship_fields).exists():
            self.inverse_relationship.save()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        SpacesRelationship.objects.filter(**self._inverse_relationship_fields).delete()

    @property
    def inverse_relationship(self) -> Self:
        return SpacesRelationship(**self._inverse_relationship_fields)

    @property
    def _inverse_relationship_fields(self) -> dict:
        return {
            "from_space": self.to_space,
            "to_space": self.from_space,
            "relationship_type": SpacesRelationshipType(self.relationship_type).inverse,
        }
