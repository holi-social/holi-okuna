import uuid

from django.test import testcases

from openbook_common.utils.helpers import extract_usernames_from_string


class UserMentionsParsingTestCase(testcases.TestCase):
    def test_empty_string_has_no_mentions(self):
        usernames = extract_usernames_from_string("")
        self.assertEqual(usernames, [])

    def test_string_without_mentions_has_no_mentions(self):
        usernames = extract_usernames_from_string("This is just a text")
        self.assertEqual(usernames, [])

    def test_uuid_without_at_is_no_mention(self):
        user_id = str(uuid.uuid4())
        usernames = extract_usernames_from_string(f"This is no {user_id} Mention")
        self.assertEqual(usernames, [])

    def test_string_with_uuid_is_parsed(self):
        user_id = str(uuid.uuid4())
        usernames = extract_usernames_from_string(f"This is a @{user_id} Mention")
        self.assertEqual(usernames, [user_id])

    def test_uuid_is_parsed_without_pre_and_postfix_characters(self):
        user_id = str(uuid.uuid4())
        usernames = extract_usernames_from_string(f"This is a@{user_id}553 Mention")
        self.assertEqual(usernames, [user_id])

    def test_uuid_is_parsed_ignoring_case(self):
        user_id = "Dfa78f20-f7E9-41d4-aFcF-2ae437153922"
        usernames = extract_usernames_from_string(f"This is a@{user_id}553 Mention")
        self.assertEqual(usernames, [user_id])
