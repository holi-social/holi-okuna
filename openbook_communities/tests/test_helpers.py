from rest_framework.exceptions import ValidationError

from openbook_common.tests.helpers import make_community
from openbook_common.tests.models import OpenbookAPITestCase
from openbook_communities.helpers import create_community_name_from_title_and_hash


class CommunitiesHelperTests(OpenbookAPITestCase):
    def test_create_community_name_from_title_and_hash(self):
        hash = "1234567890"
        long_name = "f" * 60
        make_community(title="bar")
        make_community(title="bar-12345678")
        make_community(title=long_name)

        self.assertEqual("", create_community_name_from_title_and_hash("", hash))
        self.assertEqual("foo", create_community_name_from_title_and_hash("FOO", hash))
        self.assertEqual("foo-bar", create_community_name_from_title_and_hash(" Foo Bar ", hash))
        self.assertEqual("foobar", create_community_name_from_title_and_hash("Foo%$&bar", hash))
        self.assertEqual("bar-23456789", create_community_name_from_title_and_hash("bar", "2345678901"))
        self.assertEqual("bar-123456789", create_community_name_from_title_and_hash("bar", hash))
        self.assertEqual("bar-1234", create_community_name_from_title_and_hash("bar", "1234"))
        self.assertEqual(f"{long_name[:51]}-12345678", create_community_name_from_title_and_hash(long_name, hash))

        with self.assertRaises(Exception) as context:
            create_community_name_from_title_and_hash("bar", "12345678")
        self.assertTrue("Community name already taken." in str(context.exception))
        with self.assertRaises(Exception) as context:
            create_community_name_from_title_and_hash("bar", "")
        self.assertTrue("Community name already taken." in str(context.exception))
