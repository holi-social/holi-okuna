from typing import List
from enum import Enum

from openbook_notifications.payloads import SpaceMembershipRequestPayload
from openbook_notifications.toggles import notifications_toggle

from novu.api import EventApi


class Notification:
    def __init__(
        self,
        workflow: str,
        recipients: str | List[str],
        payload: dict,
    ):
        self.workflow = workflow
        self.recipients = recipients
        self.payload = payload

    @notifications_toggle
    def send(self):
        return EventApi().trigger(name=self.workflow, recipients=self.recipients, payload=self.payload)
