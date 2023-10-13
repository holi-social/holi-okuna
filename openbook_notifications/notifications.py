from requests import Session
from requests.adapters import HTTPAdapter, Retry

from typing import List

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
        self.session = self.create_session()

    def create_session(self):
        session = Session()
        retries = Retry(
            total=5,  # Number of retries
            backoff_factor=1,  # Delay between retries (exponential backoff)
            status_forcelist=[502, 503, 504],  # Include common error codes
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)
        return session

    @notifications_toggle
    def send(self):
        return EventApi(session=self.session).trigger(
            name=self.workflow, recipients=self.recipients, payload=self.payload
        )
