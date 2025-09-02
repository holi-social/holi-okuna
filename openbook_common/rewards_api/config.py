import os
from dataclasses import dataclass
from typing import Self


@dataclass
class Config:
    base_url: str

    @classmethod
    def from_env(cls) -> Self:
        return cls(
            base_url=os.getenv("REWARDS_API_BASE_URL"),
        )

    @property
    def events_url(self):
        return f"{self.base_url}/events"
