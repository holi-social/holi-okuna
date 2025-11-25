from django.apps import AppConfig
from django.db.models.signals import post_save

from petitions.signals import publish_external_petition_signed


class PetitionsConfig(AppConfig):
    name = "petitions"

    def ready(self):
        post_save.connect(
            publish_external_petition_signed,
            sender="petitions.PetitionStatus",
            dispatch_uid="publish_external_petition_signed",
        )
