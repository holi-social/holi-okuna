import uuid

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from openbook_common.tests.helpers import make_user
from volunteering.models import VolunteeringOpportunityStatus, Status
from volunteering.tests.helpers import (
    list_committed_volunteering_opportunities,
    update_volunteering_opportunity_status,
    get_volunteering_opportunity_status,
)


@pytest.mark.django_db
class TestVolunteeringGraphQL(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()
        cls.external_volunteering_opportunity_id = uuid.uuid4()

    def test_can_not_list_volunteering_opportunity_statuses_when_not_logged_in(self):
        """
        Given: A user is not logged in
        When: Listing volunteering opportunity statuses
        Then: An error is returned and no volunteering opportunity statuses are returned
        """
        response = list_committed_volunteering_opportunities(user=AnonymousUser)

        assert response.errors is not None
        assert response.data is None
        assert "Unauthorized" in str(response.errors[0].message)

    def test_listing_volunteering_opportunity_statuses_returns_empty_list_when_none_saved(self):
        """
        Given: A user has not committed to any volunteering opportunity
        When: Listing volunteering opportunity statuses
        Then: An empty list is returned
        """
        response = list_committed_volunteering_opportunities(user=self.user)

        assert response.errors is None
        assert response.data is not None

        assert response.data["committedVolunteeringOpportunities"]["totalResults"] == 0
        assert response.data["committedVolunteeringOpportunities"]["data"] == []

    def test_listing_volunteering_opportunity_statuses_returns_list_when_some_saved(self):
        """
        Given: A user has committed to one volunteering opportunity
        When: Listing volunteering opportunity statuses
        Then: The volunteering opportunity status is returned in the list
        """
        self._make_volunteering_opportunity_status()

        response = list_committed_volunteering_opportunities(user=self.user)

        assert response.errors is None
        assert response.data is not None
        assert response.data["committedVolunteeringOpportunities"]["totalResults"] == 1
        assert response.data["committedVolunteeringOpportunities"]["data"] == [
            {
                "status": "TO_DO",
                "externalVolunteeringOpportunityId": str(self.external_volunteering_opportunity_id),
            }
        ]

    def test_commit_to_new_volunteering_opportunity_sets_to_do(self):
        """
        Given: A user wants to commit to a volunteering opportunity
        When: Committing to a volunteering opportunity
        Then: The status is always set to TO_DO
        """
        response = update_volunteering_opportunity_status(
            user=self.user,
            volunteering_opportunity_id=self.external_volunteering_opportunity_id,
        )

        assert response.errors is None
        assert response.data is not None
        assert response.data["updateVolunteeringOpportunityStatus"]["status"] == Status.TO_DO.value

    def test_transitioning_volunteering_opportunity_status_forward_works(self):
        """
        Given: A user has committed to a volunteering opportunity
        When: The volunteer transitions the volunteering opportunity status forward to a valid new status
        Then: The volunteer's status is updated to the new status
        """
        test_combinations = [
            (Status.TO_DO, Status.CONTACTED),
            (Status.TO_DO, Status.WONT_DO),
            (Status.CONTACTED, Status.DOING),
            (Status.CONTACTED, Status.WONT_DO),
            (Status.DOING, Status.DONE),
            (Status.DOING, Status.WONT_DO),
        ]

        for existing_status, new_status in test_combinations:
            vo_status = self._make_volunteering_opportunity_status(existing_status)

            response = update_volunteering_opportunity_status(
                user=self.user,
                volunteering_opportunity_id=self.external_volunteering_opportunity_id,
                new_status=new_status,
            )

            assert response.errors is None
            assert response.data is not None
            assert response.data["updateVolunteeringOpportunityStatus"]["status"] == new_status.value

            vo_status.delete()

    def test_can_not_get_volunteering_opportunity_status_when_not_logged_in(self):
        """
        Given: A user is not logged in
        When: Getting a volunteering opportunity status
        Then: An error is returned and no volunteering opportunity status is returned
        """
        response = get_volunteering_opportunity_status(
            user=AnonymousUser,
            volunteering_opportunity_id=self.external_volunteering_opportunity_id,
        )

        assert response.errors is not None
        assert "Unauthorized" in str(response.errors[0].message)

    def test_get_volunteering_opportunity_status_returns_none_when_not_found(self):
        """
        Given: A user has not committed to a volunteering opportunity
        When: Getting the volunteering opportunity status
        Then: None is returned
        """
        response = get_volunteering_opportunity_status(
            user=self.user,
            volunteering_opportunity_id=self.external_volunteering_opportunity_id,
        )

        assert response.errors is None
        assert response.data is not None
        assert response.data["volunteeringOpportunityStatus"] is None

    def test_get_volunteering_opportunity_status_returns_status_when_found(self):
        """
        Given: A user has committed to a volunteering opportunity
        When: Getting the volunteering opportunity status
        Then: The volunteering opportunity status is returned
        """
        self._make_volunteering_opportunity_status()

        response = get_volunteering_opportunity_status(
            user=self.user,
            volunteering_opportunity_id=self.external_volunteering_opportunity_id,
        )

        assert response.errors is None
        assert response.data is not None
        assert response.data["volunteeringOpportunityStatus"] == {
            "status": "TO_DO",
            "externalVolunteeringOpportunityId": str(self.external_volunteering_opportunity_id),
        }

    def test_invalid_status_transition_returns_error(self):
        """
        Given: A user has a volunteering opportunity with status TO_DO
        When: Attempting to update the status to DONE (invalid transition)
        Then: An error is returned
        """
        self._make_volunteering_opportunity_status(Status.TO_DO)

        response = update_volunteering_opportunity_status(
            user=self.user,
            volunteering_opportunity_id=self.external_volunteering_opportunity_id,
            new_status=Status.DONE,
        )

        assert response.errors is not None
        assert "Transition to this status is not allowed" in str(response.errors[0].message)
        assert "BAD_USER_INPUT" in str(response.errors[0].extensions)

    def test_update_to_same_status_is_noop(self):
        """
        Given: A user has a volunteering opportunity with status TO_DO
        When: Updating the status to TO_DO again
        Then: The operation succeeds and the status remains TO_DO
        """
        self._make_volunteering_opportunity_status(Status.TO_DO)

        response = update_volunteering_opportunity_status(
            user=self.user,
            volunteering_opportunity_id=self.external_volunteering_opportunity_id,
            new_status=Status.TO_DO,
        )

        assert response.errors is None
        assert response.data is not None
        assert response.data["updateVolunteeringOpportunityStatus"]["status"] == Status.TO_DO.value

    def test_different_user_gets_different_status(self):
        """
        Given: User A has committed to a volunteering opportunity
        When: User B queries the same volunteering opportunity
        Then: User B gets None as they haven't committed to it
        """
        self._make_volunteering_opportunity_status(Status.TO_DO)

        second_user = make_user()

        response = get_volunteering_opportunity_status(
            user=second_user,
            volunteering_opportunity_id=self.external_volunteering_opportunity_id,
        )

        assert response.errors is None
        assert response.data is not None
        assert response.data["volunteeringOpportunityStatus"] is None

    def test_different_user_creates_separate_status(self):
        """
        Given: User A has committed to a volunteering opportunity with status CONTACTED
        When: User B commits to the same volunteering opportunity
        Then: User B creates their own status record with TO_DO
        """
        self._make_volunteering_opportunity_status(Status.CONTACTED)

        second_user = make_user()

        response = update_volunteering_opportunity_status(
            user=second_user,
            volunteering_opportunity_id=self.external_volunteering_opportunity_id,
        )

        assert response.errors is None
        assert response.data is not None
        assert response.data["updateVolunteeringOpportunityStatus"]["status"] == Status.TO_DO.value

        response = get_volunteering_opportunity_status(
            user=self.user,
            volunteering_opportunity_id=self.external_volunteering_opportunity_id,
        )

        assert response.errors is None
        assert response.data is not None
        assert response.data["volunteeringOpportunityStatus"]["status"] == Status.CONTACTED.value

    def test_terminal_states_prevent_further_transitions(self):
        """
        Given: A user has a volunteering opportunity with a terminal status (DONE or WONT_DO)
        When: Attempting to update to any other status
        Then: An error is returned as transitions from terminal states are not allowed
        """
        test_combinations = [
            (Status.DONE, Status.TO_DO),
            (Status.DONE, Status.CONTACTED),
            (Status.DONE, Status.DOING),
            (Status.DONE, Status.WONT_DO),
            (Status.WONT_DO, Status.TO_DO),
            (Status.WONT_DO, Status.CONTACTED),
            (Status.WONT_DO, Status.DOING),
            (Status.WONT_DO, Status.DONE),
        ]

        for terminal_status, attempted_new_status in test_combinations:
            self._make_volunteering_opportunity_status(terminal_status)

            response = update_volunteering_opportunity_status(
                user=self.user,
                volunteering_opportunity_id=self.external_volunteering_opportunity_id,
                new_status=attempted_new_status,
            )

            assert response.errors is not None
            assert "Transition to this status is not allowed" in str(response.errors[0].message)
            assert "BAD_USER_INPUT" in str(response.errors[0].extensions)

            db_status = VolunteeringOpportunityStatus.objects.get(
                user=self.user,
                external_volunteering_opportunity_id=self.external_volunteering_opportunity_id,
            )
            assert db_status.status == terminal_status.value

            db_status.delete()

    def _make_volunteering_opportunity_status(self, status: Status = Status.TO_DO):
        vo_status = VolunteeringOpportunityStatus(
            external_volunteering_opportunity_id=self.external_volunteering_opportunity_id,
            user=self.user,
            status=status.value,
        )

        vo_status.save()
        return vo_status
