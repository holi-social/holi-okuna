from importlib import import_module
import pytest
from django.apps import apps
from django.db import connection
from openbook_auth.models import User
from openbook_common.tests.helpers import make_user, make_topic, make_skill
# Required because of file name starting with a number
migration = import_module('openbook_auth.migrations.0035_userprofile_interests_v2_userprofile_skills_v2')

@pytest.mark.django_db
class TestMigrateUserProfileTopicsAndSkills:
    def test_migrate_topics_and_skills(self):
        # GIVEN a user with only V1 interests and skills
        interests_v1 = [make_topic(slug="eco-tourism"), make_topic(slug="elderly-people")]
        skills_v1 = [make_skill(slug="writing-translation"), make_skill(slug="assertiveness")]
        user = make_user(interests=[], skills=[], interests_v2=[], skills_v2=[])
        user.profile.interests.set(interests_v1)
        user.profile.skills.set(skills_v1)

        # WHEN migrating user profile interests and skills from V1 to V2
        migration.migrate_topics_and_skills(apps, connection.schema_editor())

        # THEN the user has mapped V2 interests and skills
        updated_profile = User.objects.get(username=user.username).profile
        assert sorted(updated_profile.interests_v2) == sorted(["lifestyle-consumption", "elderly-care"])
        assert sorted(updated_profile.skills_v2) == sorted(["translation", "other"])
