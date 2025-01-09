from django.db.models import QuerySet

from openbook.settings import COMMUNITY_NAME_MAX_LENGTH
from openbook_auth.models import UserRole
from openbook_common.tests.helpers import make_community, make_user
from openbook_common.tests.models import OpenbookAPITestCase
from openbook_communities.helpers import create_community_name_from_title_and_hash, get_space_representatives
from openbook_communities.models import CommunityMembership


class CommunitiesHelperTests(OpenbookAPITestCase):
    def test_create_community_name_from_title_and_hash(self):
        hash = "1234567890"
        long_name = "f" * COMMUNITY_NAME_MAX_LENGTH
        make_community(title="bar")
        make_community(title="Some Title")
        make_community(title="bar-12345678")
        make_community(title=long_name)

        self.assertEqual("", create_community_name_from_title_and_hash("", hash))
        self.assertEqual("foo", create_community_name_from_title_and_hash("FOO", hash))
        self.assertEqual("foo-bar", create_community_name_from_title_and_hash(" Foo Bar ", hash))
        self.assertEqual("foobar", create_community_name_from_title_and_hash("Foo%$&bar", hash))
        self.assertEqual("some-title-23456789", create_community_name_from_title_and_hash("Some Title", "2345678901"))
        self.assertEqual("bar-123456789", create_community_name_from_title_and_hash("bar", hash))
        self.assertEqual("bar-1234", create_community_name_from_title_and_hash("bar", "1234"))
        self.assertEqual(f"{long_name[:71]}-12345678", create_community_name_from_title_and_hash(long_name, hash))

        with self.assertRaises(Exception) as context:
            create_community_name_from_title_and_hash("bar", "12345678")
        self.assertTrue("Community name already taken." in str(context.exception))
        with self.assertRaises(Exception) as context:
            create_community_name_from_title_and_hash("bar", "")
        self.assertTrue("Community name already taken." in str(context.exception))

    def test_space_representatives_filters_internal_users(self) -> None:
        """
        Given: a space with a mix of internal and external admins
        When: requesting the space representatives
        Then: only external users are returned
        """

        external_user = make_user()
        internal_role_user = make_user(role=UserRole.INTERNAL)
        employee_user = make_user(is_employee=True)

        space = make_community(
            creator=external_user,
            admins=[employee_user, internal_role_user],  # admins are *in addition* to the creator
        )

        representatives: QuerySet[CommunityMembership] = get_space_representatives(space)

        self.assertEqual(representatives.count(), 1)
        self.assertEqual(representatives.first().user.pk, external_user.pk)

    def test_space_representatives_uses_internal_users_as_fallback(self) -> None:
        """
        Given: a space with only internal users as admins
        When: requesting the space representatives
        Then: internal admins are returned
        """

        creator = make_user(role=UserRole.INTERNAL)
        admin1 = make_user(role=UserRole.INTERNAL, is_employee=True)
        admin2 = make_user(is_employee=True)

        space = make_community(
            creator=creator,
            admins=[admin1, admin2],
        )

        representatives: QuerySet[CommunityMembership] = get_space_representatives(space)

        self.assertEqual(representatives.count(), 3)
        self.assertEqual(
            list(representatives.values_list("user__pk", flat=True)),
            [creator.pk, admin1.pk, admin2.pk],
        )
