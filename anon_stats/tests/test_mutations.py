import pytest
from asgiref.sync import async_to_sync

from anon_stats.models import Counter
from openbook.graphql_schema import schema
from unittest import mock


@pytest.mark.django_db
class TestAnonCountMutation:
    @staticmethod
    def _increment_count(counter_name):
        mutation = f"""
            mutation {{
                anonCount(counterName: "{counter_name}")
            }}
        """

        response = async_to_sync(schema.execute)(mutation)
        assert response.errors is None

    @staticmethod
    def _validate_counts(counter_name, expected_count):
        counters = Counter.objects.filter(name=counter_name)
        assert counters.exists() == (expected_count > 0)
        assert counters.count() == expected_count, "Unexpected number of counts created"
        for counter in counters:
            assert counter.name == counter_name, "Counter name mismatch"

    def test_anon_count_creates_counter(self):
        self._increment_count("test_counter")
        self._validate_counts("test_counter", 1)

        self._increment_count("test_counter")
        self._validate_counts("test_counter", 2)

    def test_anon_count_supports_multiple_counters(self):
        self._increment_count("test_counter")
        self._increment_count("other_test_counter")
        self._validate_counts("test_counter", 1)
        self._validate_counts("other_test_counter", 1)

        self._increment_count("other_test_counter")
        self._validate_counts("other_test_counter", 2)

    def test_anon_count_empty_name(self):
        self._increment_count(" ")
        self._validate_counts("", 0)
        self._validate_counts(" ", 0)

    @mock.patch("anon_stats.models.Counter.objects.acreate")
    def test_anon_count_handles_database_exceptions(self, mock_acreate):
        mock_acreate.side_effect = Exception("Database error")

        self._increment_count("test_counter")

        counters = Counter.objects.filter(name="test_counter")
        assert not counters.exists(), "Counter should not be created when there is a database exception"
