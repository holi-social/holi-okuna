import pytest
from django.utils import timezone

from openbook_common.models import FeatureToggle, FeatureToggleType


@pytest.mark.django_db
class TestFeatureToggleModel:
    feature_toggle_name = "Test Toggle"

    def test_create_feature_toggle_success(self):
        feature_toggle = FeatureToggle.objects.create(
            name=self.feature_toggle_name,
            status=FeatureToggleType.PRODUCTION,
        )

        saved_toggle = FeatureToggle.objects.get(name=feature_toggle.name)

        assert saved_toggle.name == self.feature_toggle_name
        assert saved_toggle.status == FeatureToggleType.PRODUCTION
        assert saved_toggle.created is not None
        assert saved_toggle.created <= timezone.now()

    def test_create_feature_toggle_error_duplicate(self):
        FeatureToggle.objects.create(
            name=self.feature_toggle_name,
            status=FeatureToggleType.PREVIEW,
        )

        with pytest.raises(Exception):  # noqa: B017
            FeatureToggle.objects.create(
                name=self.feature_toggle_name,
                status=FeatureToggleType.PRODUCTION,
            )

    def test_update_feature_toggle_success(self):
        feature_toggle = FeatureToggle.objects.create(
            name=self.feature_toggle_name,
            status=FeatureToggleType.PRODUCTION,
        )

        feature_toggle.status = FeatureToggleType.MAINTENANCE
        feature_toggle.save()

        updated_toggle = FeatureToggle.objects.get(id=feature_toggle.id)

        assert updated_toggle.name == feature_toggle.name
        assert updated_toggle.status == FeatureToggleType.MAINTENANCE
