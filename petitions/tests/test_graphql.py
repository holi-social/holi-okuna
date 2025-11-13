import uuid

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from openbook_common.tests.helpers import make_user
from petitions.models import PetitionStatus, Status
from petitions.tests.helpers import (
    list_signed_petitions,
    update_petition_status,
    get_petition_status,
)


@pytest.mark.django_db
class TestPetitionsGraphQL(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()
        cls.external_petition_id = str(uuid.uuid4())

    def test_can_not_list_petitions_when_not_logged_in(self):
        """
        Given: A user is not logged in
        When: Listing signed petitions
        Then: An error is returned and no petitions are returned
        """
        response = list_signed_petitions(user=AnonymousUser)

        assert response.errors is not None
        assert response.data is None
        assert "Unauthorized" in str(response.errors[0].message)

    def test_listing_petitions_returns_empty_list_when_none_saved(self):
        """
        Given: A user has not signed any petition
        When: Listing signed petitions
        Then: An empty list is returned
        """
        response = list_signed_petitions(user=self.user)

        assert response.errors is None
        assert response.data is not None

        assert response.data["signedPetitions"]["totalResults"] == 0
        assert response.data["signedPetitions"]["data"] == []

    def test_listing_petitions_returns_list_when_some_saved(self):
        """
        Given: A user has signed one petition
        When: Listing signed petitions
        Then: The petition status is returned in the list
        """
        self._make_petition_status()

        response = list_signed_petitions(user=self.user)

        assert response.errors is None
        assert response.data is not None
        assert response.data["signedPetitions"]["totalResults"] == 1
        assert response.data["signedPetitions"]["data"] == [
            {
                "status": "PLANNED",
                "externalPetitionId": str(self.external_petition_id),
            }
        ]

    def test_commit_to_new_petition_sets_planned(self):
        """
        Given: A user wants to commit to a petition
        When: Committing to a petition
        Then: The status is always set to PLANNED
        """
        response = update_petition_status(
            user=self.user,
            petition_id=self.external_petition_id,
        )

        assert response.errors is None
        assert response.data is not None
        assert response.data["updatePetitionStatus"]["status"] == Status.PLANNED.value

    def test_transitioning_petition_status_forward_works(self):
        """
        Given: A user has committed to a petition
        When: The user transitions the petition status forward to a valid new status
        Then: The user's status is updated to the new status
        """
        test_combinations = [
            (Status.PLANNED, Status.SIGNED),
        ]

        for existing_status, new_status in test_combinations:
            petition_status = self._make_petition_status(existing_status)

            response = update_petition_status(
                user=self.user,
                petition_id=self.external_petition_id,
                new_status=new_status,
            )

            assert response.errors is None
            assert response.data is not None
            assert response.data["updatePetitionStatus"]["status"] == new_status.value

            petition_status.delete()

    def test_can_not_get_petition_status_when_not_logged_in(self):
        """
        Given: A user is not logged in
        When: Getting a petition status
        Then: An error is returned and no petition status is returned
        """
        response = get_petition_status(
            user=AnonymousUser,
            petition_id=self.external_petition_id,
        )

        assert response.errors is not None
        assert "Unauthorized" in str(response.errors[0].message)

    def test_get_petition_status_returns_none_when_not_found(self):
        """
        Given: A user has not committed to a petition
        When: Getting the petition status
        Then: None is returned
        """
        response = get_petition_status(
            user=self.user,
            petition_id=self.external_petition_id,
        )

        assert response.errors is None
        assert response.data is not None
        assert response.data["petitionStatus"] is None

    def test_get_petition_status_returns_status_when_found(self):
        """
        Given: A user has committed to a petition
        When: Getting the petition status
        Then: The petition status is returned
        """
        self._make_petition_status()

        response = get_petition_status(
            user=self.user,
            petition_id=self.external_petition_id,
        )

        assert response.errors is None
        assert response.data is not None
        assert response.data["petitionStatus"] == {
            "status": "PLANNED",
            "externalPetitionId": str(self.external_petition_id),
        }

    def test_invalid_status_transition_returns_error(self):
        """
        Given: A user has a petition with status PLANNED
        When: Attempting to update the status to SIGNED then back to PLANNED (invalid transition)
        Then: An error is returned
        """
        self._make_petition_status(Status.PLANNED)

        # First transition to SIGNED (valid)
        response = update_petition_status(
            user=self.user,
            petition_id=self.external_petition_id,
            new_status=Status.SIGNED,
        )

        assert response.errors is None

        # Then try to go back to PLANNED (invalid)
        response = update_petition_status(
            user=self.user,
            petition_id=self.external_petition_id,
            new_status=Status.PLANNED,
        )

        assert response.errors is not None
        assert "Transition to this status is not allowed" in str(response.errors[0].message)
        assert "BAD_USER_INPUT" in str(response.errors[0].extensions)

    def test_update_to_same_status_is_noop(self):
        """
        Given: A user has a petition with status PLANNED
        When: Updating the status to PLANNED again
        Then: The operation succeeds and the status remains PLANNED
        """
        self._make_petition_status(Status.PLANNED)

        response = update_petition_status(
            user=self.user,
            petition_id=self.external_petition_id,
            new_status=Status.PLANNED,
        )

        assert response.errors is None
        assert response.data is not None
        assert response.data["updatePetitionStatus"]["status"] == Status.PLANNED.value

    def test_different_user_gets_different_status(self):
        """
        Given: User A has committed to a petition
        When: User B queries the same petition
        Then: User B gets None as they haven't committed to it
        """
        self._make_petition_status(Status.PLANNED)

        second_user = make_user()

        response = get_petition_status(
            user=second_user,
            petition_id=self.external_petition_id,
        )

        assert response.errors is None
        assert response.data is not None
        assert response.data["petitionStatus"] is None

    def test_different_user_creates_separate_status(self):
        """
        Given: User A has committed to a petition with status SIGNED
        When: User B commits to the same petition
        Then: User B creates their own status record with PLANNED
        """
        self._make_petition_status(Status.SIGNED)

        second_user = make_user()

        response = update_petition_status(
            user=second_user,
            petition_id=self.external_petition_id,
        )

        assert response.errors is None
        assert response.data is not None
        assert response.data["updatePetitionStatus"]["status"] == Status.PLANNED.value

        response = get_petition_status(
            user=self.user,
            petition_id=self.external_petition_id,
        )

        assert response.errors is None
        assert response.data is not None
        assert response.data["petitionStatus"]["status"] == Status.SIGNED.value

    def test_terminal_states_prevent_further_transitions(self):
        """
        Given: A user has a petition with a terminal status (SIGNED)
        When: Attempting to update to any other status
        Then: An error is returned as transitions from terminal states are not allowed
        """
        test_combinations = [
            (Status.SIGNED, Status.PLANNED),
        ]

        for terminal_status, attempted_new_status in test_combinations:
            self._make_petition_status(terminal_status)

            response = update_petition_status(
                user=self.user,
                petition_id=self.external_petition_id,
                new_status=attempted_new_status,
            )

            assert response.errors is not None
            assert "Transition to this status is not allowed" in str(response.errors[0].message)
            assert "BAD_USER_INPUT" in str(response.errors[0].extensions)

            db_status = PetitionStatus.objects.get(
                user=self.user,
                external_petition_id=self.external_petition_id,
            )
            assert db_status.status == terminal_status.value

            db_status.delete()

    def _make_petition_status(self, status: Status = Status.PLANNED):
        petition_status = PetitionStatus(
            external_petition_id=self.external_petition_id,
            user=self.user,
            status=status.value,
        )

        petition_status.save()
        return petition_status
