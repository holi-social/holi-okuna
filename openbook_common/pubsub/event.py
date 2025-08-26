import json
from abc import ABC, abstractmethod


class Event(ABC):
    def __init__(self, data: dict, event_type: str, event_version: str, additional_attributes: dict[str, str] = None):
        self.data = data
        self.event_type = event_type
        self.event_version = event_version
        self.additional_attributes = additional_attributes or {}

    @abstractmethod
    def log_str(self) -> str:
        """
        Returns a string that can safely be-used in logging statements without e.g. leaking PII
        """
        pass

    @property
    def encoded_data(self):
        return json.dumps(self.data).encode("utf-8")

    def to_dict(self) -> dict:
        return {
            "data": self.encoded_data,
            "eventType": self.event_type,
            "eventVersion": self.event_version,
        }
