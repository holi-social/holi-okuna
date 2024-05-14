from django.test import TestCase

from openbook_common.tests.assertions import TestAssertionsMixin
from openbook_common.tests.helpers import (
    make_fake_question_text,
    make_user,
)
from openbook_common.utils.model_loaders import get_poll_model


class PollModelTest(TestAssertionsMixin, TestCase):
    fixtures = ["openbook_moderation/fixtures/moderation_categories.json"]

    def test_create_poll_success(self):
        space_creator = make_user()

        question_text = make_fake_question_text()

        Poll = get_poll_model()

        poll = Poll.create_poll(
            creator=space_creator,
            question_text=question_text,
            created=None,
            is_draft=False,
            is_public=True,
        )

        self.assertEqual(poll.question_text, question_text)
        self.assertTrue(poll.is_public)
