from django.apps import AppConfig


class OpenbookCommunitiesConfig(AppConfig):
    name = "openbook_communities"

    def ready(self):
        from openbook_communities import signals
