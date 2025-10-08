from importlib import import_module
import pytest
from django.apps import apps
from django.db import connection
from openbook_auth.models import User, AccountType
from openbook_common.tests.helpers import make_user

# Required because of file name starting with a number
migration = import_module("openbook_auth.migrations.0040_user_account_type")


@pytest.mark.django_db
class TestUserAccountTypeMigration:
    def test_migrate_user_account_type(self):
        # GIVEN two users: oidc and none-oidc
        google_user = make_user()
        google_user.is_oidc = True
        google_user.save()
        email_user = make_user()

        # WHEN migrating user account types
        migration.migrate_account_type(apps, connection.schema_editor())

        # THEN the users have correct account types
        updated_google_user = User.objects.get(username=google_user.username)
        updated_email_user = User.objects.get(username=email_user.username)
        assert updated_google_user.account_type == AccountType.GOOGLE
        assert updated_email_user.account_type == AccountType.EMAIL
