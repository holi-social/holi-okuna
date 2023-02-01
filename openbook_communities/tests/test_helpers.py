from openbook_common.tests.models import OpenbookAPITestCase

from openbook_communities.helpers import create_community_name_from_title


class CommunitiesHelperTests(OpenbookAPITestCase):
    def test_create_community_name_from_title(self):
        self.assertEqual("", create_community_name_from_title(""))
        self.assertEqual("foo", create_community_name_from_title("FOO"))
        self.assertEqual("_foo_bar_", create_community_name_from_title(" Foo Bar "))
        self.assertEqual("foobar", create_community_name_from_title("Foo%$&bar"))
