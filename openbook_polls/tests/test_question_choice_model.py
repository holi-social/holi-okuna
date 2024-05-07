from django.test import TestCase

from openbook_common.tests.assertions import TestAssertionsMixin
from openbook_common.tests.helpers import (
    make_fake_question_text,
    make_user,
)
from openbook_common.utils.model_loaders import get_question_model


class PollModelTest(TestAssertionsMixin, TestCase):
    fixtures = ["openbook_moderation/fixtures/moderation_categories.json"]

    def test_create_question_success(self):
        space_creator = make_user()

        question_text = make_fake_question_text()

        Question = get_question_model()

        question = Question.create_question(
            creator=space_creator,
            question_text=question_text,
            created=None,
            is_draft=False,
            is_public=True,
        )

        self.assertEqual(question.question_text, question_text)
        self.assertTrue(question.is_public)
