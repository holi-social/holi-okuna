from django.apps import AppConfig
from django.db.models.signals import post_save

from volunteering.signals import publish_external_volunteering_opportunity_started


class VolunteeringConfig(AppConfig):
    name = "volunteering"

    def ready(self):
        post_save.connect(
            publish_external_volunteering_opportunity_started,
            sender="volunteering.VolunteeringOpportunityStatus",
            dispatch_uid="publish_external_volunteering_opportunity_started",
        )
