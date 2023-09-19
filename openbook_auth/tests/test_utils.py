from django.test.testcases import TestCase

from openbook_auth.utils import normalize_spaces


class NormalizeSpacesTestCase(TestCase):
    def test_normalize_spaces_with_spaces_and_text(self):
        input_string = "   Benedict Timothy  Carlton    Cumberbatch   "
        expected_output = "Benedict Timothy Carlton Cumberbatch"

        output = normalize_spaces(input_string)
        assert output == expected_output
