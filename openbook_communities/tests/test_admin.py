from unittest.mock import patch, Mock
from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model

from openbook_common.tests.helpers import make_user, make_community, make_community_task
from openbook_communities.admin import CommunityAdmin, CommunityTaskAdmin
from openbook_communities.models import Community, Task

User = get_user_model()


def saved_to_db(entity):
    """
    Checks if an entity has already been saved to the database.

    The canonical way in Django is to check for the existence of the primary key (instance.pk), but for some reason
    the property is already not None after instance creation in our codebase (hypothesis: related to extending
    ModelWithUUID).

    Warning: this uses Django internal APIs and might break in the future.
    """
    return entity._state.adding is False


class CommunityAdminTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = make_user()
        self.site = AdminSite()
        self.model_admin = CommunityAdmin(Community, self.site)
        self.community = make_community(creator=self.user)

    @patch("openbook_communities.admin.publish_space_updated_event")
    @patch("openbook_communities.admin.publish_space_created_event")
    def test_save_model_new_community_calls_publish_space_created_event(
        self, mock_publish_space_created_event, mock_publish_space_updated_event
    ):
        community = Community(
            name="test_community",
            title="Test Community",
            creator=self.user,
            type="P",  # PUBLIC
            rules="Test rules",
        )

        request = self.factory.post("/admin/openbook_communities/community/add/")
        request.user = self.user

        self.model_admin.save_model(request, community, form=None, change=False)

        assert saved_to_db(community)
        mock_publish_space_created_event.assert_called_once_with(community)
        mock_publish_space_updated_event.assert_not_called()

    @patch("openbook_communities.admin.publish_space_updated_event")
    @patch("openbook_communities.admin.publish_space_created_event")
    def test_save_model_existing_community_calls_publish_space_updated_event(
        self, mock_publish_space_created_event, mock_publish_space_updated_event
    ):
        request = self.factory.post(f"/admin/openbook_communities/community/{self.community.pk}/change/")
        request.user = self.user

        self.model_admin.save_model(request, self.community, form=None, change=True)

        mock_publish_space_created_event.assert_not_called()
        mock_publish_space_updated_event.assert_called_once_with(self.community)

    @patch("openbook_communities.admin.publish_space_deleted_event")
    @patch("openbook_communities.admin.publish_space_updated_event")
    @patch("openbook_communities.admin.publish_space_created_event")
    def test_delete_model_calls_publish_space_deleted_event(
        self, mock_publish_space_created_event, mock_publish_space_updated_event, mock_publish_space_deleted_event
    ):
        request = self.factory.post(f"/admin/openbook_communities/community/{self.community.pk}/delete/")
        request.user = self.user

        self.model_admin.delete_model(request, self.community)

        mock_publish_space_created_event.assert_not_called()
        mock_publish_space_updated_event.assert_not_called()
        mock_publish_space_deleted_event.assert_called_once_with(self.community)

    @patch("openbook_communities.admin.publish_space_created_event")
    def test_save_model_preserves_existing_behavior(self, mock_publish_space_created_event):
        community = Community(
            name="test_community_behavior",
            title="Test Community Behavior",
            creator=self.user,
            type="P",  # PUBLIC
            rules="Test rules",
        )

        request = self.factory.post("/admin/openbook_communities/community/add/")
        request.user = self.user

        assert not saved_to_db(community)
        self.model_admin.save_model(request, community, form=None, change=False)
        assert saved_to_db(community)

        membership = community.memberships.filter(user=self.user).first()
        self.assertIsNotNone(membership)
        self.assertTrue(membership.is_administrator)

    @patch("openbook_communities.admin.publish_space_updated_event")
    def test_save_model_with_form_data(self, mock_publish_space_updated_event):
        form = Mock()
        form.save.return_value = self.community

        request = self.factory.post(f"/admin/openbook_communities/community/{self.community.pk}/change/")
        request.user = self.user

        self.community.title = "Updated Title"
        self.model_admin.save_model(request, self.community, form=form, change=True)
        mock_publish_space_updated_event.assert_called_once_with(self.community)

    @patch("openbook_communities.admin.publish_space_created_event")
    def test_save_model_event_publishing_exceptions_dont_break_save(self, mock_publish_space_created_event):
        mock_publish_space_created_event.side_effect = Exception("Event publishing failed")

        community = Community(
            name="test_community_exception",
            title="Test Community Exception",
            creator=self.user,
            type="P",  # PUBLIC
            rules="Test rules",
        )

        request = self.factory.post("/admin/openbook_communities/community/add/")
        request.user = self.user

        assert not saved_to_db(community)
        self.model_admin.save_model(request, community, form=None, change=False)
        assert saved_to_db(community)

    @patch("openbook_communities.admin.publish_space_deleted_event")
    @patch("django.contrib.admin.options.ModelAdmin.delete_model")
    def test_delete_model_event_publishing_exceptions_dont_break_delete(
        self, mock_delete_model, mock_publish_space_deleted_event
    ):
        mock_publish_space_deleted_event.side_effect = Exception("Event publishing failed")

        request = self.factory.post(f"/admin/openbook_communities/community/{self.community.pk}/delete/")
        request.user = self.user

        self.model_admin.delete_model(request, self.community)

        mock_delete_model.assert_called_once_with(request, self.community)


class CommunityTaskAdminTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = make_user()
        self.site = AdminSite()
        self.model_admin = CommunityTaskAdmin(Task, self.site)
        self.community = make_community(creator=self.user)

    @patch("openbook_communities.admin.publish_task_created_event")
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
        assert saved_to_db(task)
        mock_publish_task_created_event.assert_called_once_with(self.user, task)

    @patch("openbook_communities.admin.publish_task_updated_event")
    def test_save_model_existing_task_calls_publish_task_updated_event(self, mock_publish_task_updated_event):
        task = make_community_task(
            community=self.community, creator=self.user, name="Existing Task", description="Existing Description"
        )

        request = self.factory.post(f"/admin/openbook_communities/task/{task.pk}/change/")
        request.user = self.user

        self.model_admin.save_model(request, task, form=None, change=True)
        mock_publish_task_updated_event.assert_called_once_with(self.user, task)

    @patch("openbook_communities.admin.publish_task_deleted_event")
    def test_delete_model_calls_publish_task_deleted_event(self, mock_publish_task_deleted_event):
        task = make_community_task(
            community=self.community, creator=self.user, name="Task to Delete", description="Will be deleted"
        )

        request = self.factory.post(f"/admin/openbook_communities/task/{task.pk}/delete/")
        request.user = self.user

        with patch.object(self.model_admin, "delete_model", wraps=self.model_admin.delete_model):
            self.model_admin.delete_model(request, task)
            mock_publish_task_deleted_event.assert_called_once_with(self.user, task)

    @patch("openbook_communities.admin.publish_task_created_event")
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

        assert not saved_to_db(task)
        self.model_admin.save_model(request, task, form=None, change=False)
        assert saved_to_db(task)

    @patch("openbook_communities.admin.publish_task_updated_event")
    def test_save_model_with_form_data(self, mock_publish_task_updated_event):
        task = make_community_task(community=self.community, creator=self.user)

        form = Mock()
        form.save.return_value = task

        request = self.factory.post(f"/admin/openbook_communities/task/{task.pk}/change/")
        request.user = self.user

        self.model_admin.save_model(request, task, form=form, change=True)
        mock_publish_task_updated_event.assert_called_once_with(self.user, task)

    @patch("openbook_communities.admin.publish_task_created_event")
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

        assert not saved_to_db(task)
        self.model_admin.save_model(request, task, form=None, change=False)
        assert saved_to_db(task)

    @patch("openbook_communities.admin.publish_task_deleted_event")
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
