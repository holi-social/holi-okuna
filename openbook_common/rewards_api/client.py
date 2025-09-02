from abc import ABC, abstractmethod

from requests import Session

from .config import Config
from .event import Event


class Client(ABC):
    config: Config

    def __init__(self, config: Config):
        self.config = config

    @abstractmethod
    def submit_event[Payload](self, event: Event[Payload]):
        pass


class RestClient(Client):
    config: Config
    http: Session

    @classmethod
    def from_env(cls):
        return cls(config=Config.from_env())

    def __init__(self, config: Config):
        super().__init__(config)

        self.http = Session()
        self.http.headers["Content-Type"] = "application/json"

    def submit_event[Payload](self, event: Event[Payload]):
        self.http.post(self.config.events_url, data=event.to_json())


class NoopClient(Client):
    def __init__(self):
        super().__init__(Config(base_url="http://localhost:12345"))

    def submit_event[Payload](self, event: Event[Payload]):
        pass
