import logging
from unittest import TestCase

import pytest

from openbook_common.tests.helpers import (
    make_fake_question_text,
    make_user,
)
from openbook_polls.tests.helpers import get_polls_with_id, get_poll_with_id_raw, create_poll, update_votes

logger = logging.getLogger(__name__)


@pytest.mark.django_db
class TestPolls(TestCase):
    def test_can_fetch_poll_by_id(self):
        posting_user = make_user()

        question_text = make_fake_question_text()

        poll = posting_user.create_poll(
            question_text=question_text,
            created=None,
            is_draft=False,
            is_public=True,
        )

        poll_data = get_polls_with_id(poll)

        assert poll_data["questionText"] == question_text
        assert poll_data["creator"]["id"] == str(posting_user.uuid)
        assert poll_data["created"] is not None

    def test_cant_fetch_poll_draft(self):
        posting_user = make_user()

        question_text = make_fake_question_text()

        poll = posting_user.create_poll(
            question_text=question_text,
            created=None,
            is_draft=True,
            is_public=True,
        )

        response = get_poll_with_id_raw(poll.id)

        poll_data = response.data["pollById"]
        assert poll_data is None
        assert "Forbidden" in response.errors[0].message

    def test_cant_fetch_deleted_poll(self):
        posting_user = make_user()

        question_text = make_fake_question_text()

        question = posting_user.create_poll(
            question_text=question_text,
            is_draft=False,
            is_public=True,
        )
        question.delete()

        response = get_poll_with_id_raw(question.id)

        question_data = response.data
        assert question_data is None

    def test_user_can_create_poll(self):
        user = make_user()

        question_text = make_fake_question_text()

        input_data = {
            "questionText": question_text,
        }

        response = create_poll(user, input_data)

        poll_data = response.data["createPoll"]

        assert poll_data["questionText"] == input_data["questionText"]
        assert poll_data["isPublic"] is True

    def test_unauthorized_user_cant_vote(self):
        posting_user = make_user()

        question_text = make_fake_question_text()

        poll = posting_user.create_poll(
            question_text=question_text,
            is_draft=False,
            is_public=True,
        )

        response = update_votes(poll.id, user=None)

        assert response.data is None

    def test_user_cant_vote_with_wrong_id(self):
        posting_user = make_user()

        question_text = make_fake_question_text()

        poll = posting_user.create_poll(
            question_text=question_text,
            is_draft=False,
            is_public=True,
        )

        response = update_votes(poll.id, posting_user)

        assert response.data is None
