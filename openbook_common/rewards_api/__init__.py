from .config import Config
from .client import Client, NoopClient, RestClient
from .event import Event


def build_client():
    config = Config.from_env()
    if config.base_url is None:
        return NoopClient()

    return RestClient(config)


RewardsClient = build_client()

__all__ = ["RewardsClient", "Event", "Client"]
