from unittest.mock import patch, Mock
from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite

from openbook_common.tests.helpers import make_user
from openbook_auth.admin import UserAdmin
from openbook_auth.models import User


def saved_to_db(entity):
    """
    Checks if an entity has already been saved to the database.

    The canonical way in Django is to check for the existence of the primary key (instance.pk), but for some reason
    the property is already not None after instance creation in our codebase (hypothesis: related to extending
    ModelWithUUID).

    Warning: this uses Django internal APIs and might break in the future.
    """
    return entity._state.adding is False


class UserAdminTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.model_admin = UserAdmin(User, self.site)
        self.user = make_user()

    @patch("openbook_auth.admin.publish_user_updated_event")
    def test_save_model_calls_publish_user_updated_event(self, mock_publish_user_updated_event):
        request = self.factory.post(f"/admin/openbook_auth/user/{self.user.pk}/change/")
        request.user = self.user

        self.model_admin.save_model(request, self.user, form=None, change=True)

        mock_publish_user_updated_event.assert_called_once_with(self.user)

    @patch("openbook_auth.admin.publish_user_updated_event")
    def test_save_model_preserves_existing_behavior(self, mock_publish_user_updated_event):
        assert saved_to_db(self.user)

        request = self.factory.post(f"/admin/openbook_auth/user/{self.user.pk}/change/")
        request.user = self.user

        self.user.username = "updated_username"
        self.model_admin.save_model(request, self.user, form=None, change=True)

        assert saved_to_db(self.user)
        mock_publish_user_updated_event.assert_called_once_with(self.user)

    @patch("openbook_auth.admin.publish_user_updated_event")
    def test_save_model_with_form_data(self, mock_publish_user_updated_event):
        form = Mock()
        form.save.return_value = self.user

        request = self.factory.post(f"/admin/openbook_auth/user/{self.user.pk}/change/")
        request.user = self.user

        self.user.username = "updated_username"
        self.model_admin.save_model(request, self.user, form=form, change=True)
        mock_publish_user_updated_event.assert_called_once_with(self.user)

    @patch("openbook_auth.admin.publish_user_updated_event")
    def test_save_model_event_publishing_exceptions_dont_break_save(self, mock_publish_user_updated_event):
        mock_publish_user_updated_event.side_effect = Exception("Event publishing failed")

        request = self.factory.post(f"/admin/openbook_auth/user/{self.user.pk}/change/")
        request.user = self.user

        assert saved_to_db(self.user)
        self.model_admin.save_model(request, self.user, form=None, change=True)

        assert saved_to_db(self.user)

    @patch("openbook_auth.admin.publish_user_deleted_event")
    @patch("django.contrib.admin.options.ModelAdmin.delete_model")
    def test_delete_model_calls_publish_user_deleted_event(self, mock_delete_model, mock_publish_user_deleted_event):
        request = self.factory.post(f"/admin/openbook_auth/user/{self.user.pk}/delete/")
        request.user = self.user

        self.model_admin.delete_model(request, self.user)

        mock_delete_model.assert_called_once_with(request, self.user)
        mock_publish_user_deleted_event.assert_called_once_with(self.user)

    @patch("openbook_auth.admin.publish_user_deleted_event")
    @patch("django.contrib.admin.options.ModelAdmin.delete_model")
    def test_delete_model_event_publishing_exceptions_dont_break_delete(
        self, mock_delete_model, mock_publish_user_deleted_event
    ):
        mock_publish_user_deleted_event.side_effect = Exception("Event publishing failed")

        request = self.factory.post(f"/admin/openbook_auth/user/{self.user.pk}/delete/")
        request.user = self.user

        self.model_admin.delete_model(request, self.user)

        mock_delete_model.assert_called_once_with(request, self.user)

    @patch("openbook_auth.admin.publish_user_updated_event")
    def test_save_model_new_user_calls_publish_user_updated_event(self, mock_publish_user_updated_event):
        new_user = make_user()

        request = self.factory.post("/admin/openbook_auth/user/add/")
        request.user = self.user

        self.model_admin.save_model(request, new_user, form=None, change=False)

        assert saved_to_db(new_user)
        mock_publish_user_updated_event.assert_called_once_with(new_user)

    @patch("openbook_auth.admin.publish_user_updated_event")
    def test_save_model_existing_user_calls_publish_user_updated_event(self, mock_publish_user_updated_event):
        request = self.factory.post(f"/admin/openbook_auth/user/{self.user.pk}/change/")
        request.user = self.user

        self.model_admin.save_model(request, self.user, form=None, change=True)

        mock_publish_user_updated_event.assert_called_once_with(self.user)
