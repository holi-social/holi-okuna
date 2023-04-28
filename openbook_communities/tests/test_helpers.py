from rest_framework.exceptions import ValidationError

from openbook_common.tests.models import OpenbookAPITestCase
from openbook_common.tests.helpers import make_community

from openbook_communities.helpers import create_community_name_from_title_and_hash


class CommunitiesHelperTests(OpenbookAPITestCase):
    def test_create_community_name_from_title_and_hash(self):
        hash = "1234567890"
        long_name = "f" * 60
        make_community(title="bar")
        make_community(title="bar-12345678")
        make_community(title=long_name)

        assert "" == create_community_name_from_title_and_hash("", hash)
        assert "foo" == create_community_name_from_title_and_hash("FOO", hash)
        assert "foo-bar" == create_community_name_from_title_and_hash(" Foo Bar ", hash)
        assert "foobar" == create_community_name_from_title_and_hash("Foo%$&bar", hash)
        assert "bar-23456789" == create_community_name_from_title_and_hash("bar", "2345678901")
        assert "bar-123456789" == create_community_name_from_title_and_hash("bar", hash)
        assert "bar-1234" == create_community_name_from_title_and_hash("bar", "1234")
        assert f"{long_name[:51]}-12345678" == create_community_name_from_title_and_hash(long_name, hash)

        with self.assertRaises(Exception) as context:
            create_community_name_from_title_and_hash("bar", "12345678")
        assert "Community name already taken." in str(context.exception)
        with self.assertRaises(Exception) as context:
            create_community_name_from_title_and_hash("bar", "")
        assert "Community name already taken." in str(context.exception)
