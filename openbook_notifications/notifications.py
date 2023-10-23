from enum import Enum
from requests import Session
from requests.adapters import HTTPAdapter, Retry

from typing import List
from openbook_notifications.helpers import flatten_payload
from openbook_notifications.payloads import SpaceMembershipRequestPayload

from openbook_notifications.toggles import notifications_toggle

from novu.api import EventApi


class Workflow(Enum):
    SPACE_MEMBERSHIP_REQUEST = "space-membership-request"


class Notification:
    def __init__(
        self,
        workflow: str,
        recipients: str | List[str],
        payload: dict,
    ):
        session = Session()
        retries = Retry(
            total=5,  # Number of retries
            backoff_factor=1,  # Delay between retries (exponential backoff)
            status_forcelist=[502, 503, 504],  # Include common error codes
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)

        self.workflow = workflow
        self.recipients = recipients
        self.payload = payload
        self.session = session

        self.overrides = {
            "type": "data",  # data notification
            "fcm": {"type": "data", "data": flatten_payload(payload)},
            "apns": {"payload": {"data": flatten_payload(payload)}},
        }

    @notifications_toggle
    def send(self):
        return EventApi(session=self.session).trigger(
            name=self.workflow, recipients=self.recipients, payload=self.payload, overrides=self.overrides
        )


class SpaceMembershipRequestNotification(Notification):
    def __init__(self, recipients: str | List[str], payload: SpaceMembershipRequestPayload):
        super().__init__(
            workflow=Workflow.SPACE_MEMBERSHIP_REQUEST.value, recipients=recipients, payload=payload.to_dict()
        )
