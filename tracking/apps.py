from django.apps import AppConfig

from tracking.tracking import initialize


class TrackingConfig(AppConfig):
    name = "tracking"

    def ready(self):
        initialize()
        # TODO probably remove signals-based code once all have been emitted and tested otherwise
        # import tracking.signals  # noqa: F401 (ignore unused import. we have to make sure the signal handlers get loaded.)
