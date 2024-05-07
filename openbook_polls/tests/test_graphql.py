import logging
from unittest import TestCase

import pytest
from openbook_common.tests.helpers import (
    make_fake_question_text,
    make_user,
)

from openbook_polls.tests.helpers import (
    get_polls_with_id,
    get_poll_with_id_raw,
)

logger = logging.getLogger(__name__)


@pytest.mark.django_db
class TestPolls(TestCase):
    def test_can_fetch_poll_by_id(self):
        posting_user = make_user()

        question_text = make_fake_question_text()

        question = posting_user.create_question(
            question_text=question_text,
            created=None,
            is_draft=False,
            is_public=True,
        )

        poll_data = get_polls_with_id(question)

        assert poll_data["questionText"] == question_text
        assert poll_data["creator"]["id"] == str(posting_user.uuid)
        assert poll_data["created"] is not None

    def test_cant_fetch_poll_draft(self):
        posting_user = make_user()

        question_text = make_fake_question_text()

        question = posting_user.create_question(
            question_text=question_text,
            created=None,
            is_draft=True,
            is_public=True,
        )

        response = get_poll_with_id_raw(question.id)

        question_data = response.data["pollById"]
        assert question_data is None
        assert "Forbidden" in response.errors[0].message
