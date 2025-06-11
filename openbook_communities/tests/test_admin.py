from unittest.mock import patch, Mock
from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model

from openbook_common.tests.helpers import make_user, make_community, make_community_task
from openbook_communities.admin import CommunityTaskAdmin
from openbook_communities.models import Task

User = get_user_model()


class CommunityTaskAdminTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = make_user()
        self.site = AdminSite()
        self.model_admin = CommunityTaskAdmin(Task, self.site)
        self.community = make_community(creator=self.user)

    @patch("openbook_communities.events.publish_task_created_event")
    def test_save_model_new_task_calls_publish_task_created_event(self, mock_publish_task_created_event):
        task = Task(
            name="Test Task",
            description="Test Description",
            community=self.community,
            creator=self.user,
            visibility="PUBLIC",
            location_type="REMOTE",
            contact_email="test@example.com",
            slots_available=5,
            regularity="ONE_TIME",
        )

        request = self.factory.post("/admin/openbook_communities/task/add/")
        request.user = self.user

        self.model_admin.save_model(request, task, form=None, change=False)
        self.assertTrue(task.pk)
        mock_publish_task_created_event.assert_called_once_with(self.user, task)

    @patch("openbook_communities.events.publish_task_updated_event")
    def test_save_model_existing_task_calls_publish_task_updated_event(self, mock_publish_task_updated_event):
        task = make_community_task(
            community=self.community, creator=self.user, name="Existing Task", description="Existing Description"
        )

        request = self.factory.post(f"/admin/openbook_communities/task/{task.pk}/change/")
        request.user = self.user

        self.model_admin.save_model(request, task, form=None, change=True)
        mock_publish_task_updated_event.assert_called_once_with(self.user, task)

    @patch("openbook_communities.events.publish_task_deleted_event")
    def test_delete_model_calls_publish_task_deleted_event(self, mock_publish_task_deleted_event):
        task = make_community_task(
            community=self.community, creator=self.user, name="Task to Delete", description="Will be deleted"
        )

        request = self.factory.post(f"/admin/openbook_communities/task/{task.pk}/delete/")
        request.user = self.user

        with patch.object(self.model_admin, "delete_model", wraps=self.model_admin.delete_model):
            self.model_admin.delete_model(request, task)
            mock_publish_task_deleted_event.assert_called_once_with(self.user, task)

    @patch("openbook_communities.events.publish_task_created_event")
    def test_save_model_preserves_existing_behavior(self, mock_publish_task_created_event):
        task = Task(
            name="Test Task",
            description="Test Description",
            community=self.community,
            creator=self.user,
            visibility="PUBLIC",
            location_type="REMOTE",
            contact_email="test@example.com",
            slots_available=5,
            regularity="ONE_TIME",
        )

        request = self.factory.post("/admin/openbook_communities/task/add/")
        request.user = self.user

        self.assertIsNone(task.pk)
        self.model_admin.save_model(request, task, form=None, change=False)
        self.assertIsNotNone(task.pk)

    @patch("openbook_communities.events.publish_task_updated_event")
    def test_save_model_with_form_data(self, mock_publish_task_updated_event):
        task = make_community_task(community=self.community, creator=self.user)

        form = Mock()
        form.save.return_value = task

        request = self.factory.post(f"/admin/openbook_communities/task/{task.pk}/change/")
        request.user = self.user

        self.model_admin.save_model(request, task, form=form, change=True)
        mock_publish_task_updated_event.assert_called_once_with(self.user, task)

    @patch("openbook_communities.events.publish_task_created_event")
    def test_save_model_event_publishing_exceptions_dont_break_save(self, mock_publish_task_created_event):
        mock_publish_task_created_event.side_effect = Exception("Event publishing failed")

        task = Task(
            name="Test Task",
            description="Test Description",
            community=self.community,
            creator=self.user,
            visibility="PUBLIC",
            location_type="REMOTE",
            contact_email="test@example.com",
            slots_available=5,
            regularity="ONE_TIME",
        )

        request = self.factory.post("/admin/openbook_communities/task/add/")
        request.user = self.user

        self.model_admin.save_model(request, task, form=None, change=False)
        self.assertIsNotNone(task.pk)

    @patch("openbook_communities.events.publish_task_deleted_event")
    @patch("django.contrib.admin.options.ModelAdmin.delete_model")
    def test_delete_model_event_publishing_exceptions_dont_break_delete(
        self, mock_delete_model, mock_publish_task_deleted_event
    ):
        mock_publish_task_deleted_event.side_effect = Exception("Event publishing failed")

        task = make_community_task(community=self.community, creator=self.user)

        request = self.factory.post(f"/admin/openbook_communities/task/{task.pk}/delete/")
        request.user = self.user

        self.model_admin.delete_model(request, task)
        mock_delete_model.assert_called()
