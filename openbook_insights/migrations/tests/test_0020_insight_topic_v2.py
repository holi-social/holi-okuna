from importlib import import_module
import pytest
from django.apps import apps
from django.db import connection
from openbook_insights.models import Insight
from openbook_common.tests.helpers import make_insight, make_topic

# Required because of file name starting with a number
migration = import_module("openbook_insights.migrations.0020_insight_topic_v2")


@pytest.mark.django_db
class TestMigrateInsightTopic:
    def test_migrate_insight_topics(self):
        # GIVEN an insight with only V1 topic
        topic_v1 = make_topic(slug="eco-tourism")
        insight = make_insight()
        insight.topic = topic_v1
        insight.save()

        # WHEN migrating insight topics from V1 to V2
        migration.migrate_topics(apps, connection.schema_editor())

        # THEN the insight has a mapped V2 topic
        updated_insight = Insight.objects.get(id=insight.id)
        assert updated_insight.topic_v2 == "lifestyle-consumption"
