from importlib import import_module
import pytest
from django.apps import apps
from django.db import connection
from openbook_communities.models import Community, Task
from openbook_common.tests.helpers import make_community, make_community_task, make_topic, make_skill

# Required because of file name starting with a number
migration = import_module("openbook_communities.migrations.0043_community_topics_v2_task_skills_v2")


@pytest.mark.django_db
class TestMigrateSpaceTopicsAndTaskSkills:
    def test_migrate_space_topics(self):
        # GIVEN a space with only V1 topics
        topics_v1 = [make_topic(slug="eco-tourism"), make_topic(slug="elderly-people")]
        space = make_community(topics=[], topics_v2=[])
        space.topics.set(topics_v1)

        # WHEN migrating space topics from V1 to V2
        migration.migrate_space_topics(apps, connection.schema_editor())

        # THEN the space has mapped V2 topics
        updated_space = Community.objects.get(id=space.id)
        assert sorted(updated_space.topics_v2) == sorted(["lifestyle-consumption", "elderly-care"])

    def test_migrate_task_skills(self):
        # GIVEN a task with only V1 skills
        skills_v1 = [make_skill(slug="writing-translation"), make_skill(slug="assertiveness")]
        task = make_community_task(community=make_community(), skills=[], skills_v2=[])
        task.skills.set(skills_v1)

        # WHEN migrating task skills from V1 to V2
        migration.migrate_task_skills(apps, connection.schema_editor())

        # THEN the task has mapped V2 skills
        updated_task = Task.objects.get(id=task.id)
        assert sorted(updated_task.skills_v2) == sorted(["translation", "other"])
