import json
from abc import ABC, abstractmethod


class Event(ABC):
    def __init__(self, data: dict, event_type: str, event_version: str):
        self.data = data
        self.event_type = event_type
        self.event_version = event_version

    @abstractmethod
    def log_str(self) -> str:
        """
        Returns a string that can safely be-used in logging statements without e.g. leaking PII
        """
        pass

    def to_dict(self) -> dict:
        return {
            "data": json.dumps(self.data).encode("utf-8"),
            "eventType": self.event_type,
            "eventVersion": self.event_version,
        }
