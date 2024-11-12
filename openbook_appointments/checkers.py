from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext_lazy as _

from openbook_appointments.enums import PermissionType


class AppointmentChecker:
    def _has_admin_permission(self, user, space_id, creator_id=None):
        return user.is_administrator_of_community_with_id(community_id=space_id) or creator_id == user.id

    def _has_participant_permission(self, user, space_id, participants):
        return user.is_member_of_community_with_id(community_id=space_id) and participants.filter(id=user.id).exists()

    def _check_space_membership(self, user, space_id, action):
        if not user.is_member_of_community_with_id(community_id=space_id):
            raise PermissionDenied(_(f"You cannot {action} appointments of a space you are not a member of"))

    def _check_permission(self, user, appointment):
        creator_id = appointment.creator.id if appointment.creator else None
        space_id = appointment.space.id
        has_permission = False

        if appointment.permission == PermissionType.ADMINS:
            has_permission = self._has_admin_permission(user=user, space_id=space_id, creator_id=creator_id)
        elif appointment.permission == PermissionType.PARTICIPANTS:
            has_permission = self._has_admin_permission(
                user=user, space_id=space_id, creator_id=creator_id
            ) or self._has_participant_permission(user=user, space_id=space_id, participants=appointment.participants)

        return has_permission

    def check_can_create_appointment(self, user, invite_only, space_id):
        self._check_space_membership(user=user, space_id=space_id, action="create")

        if not user.is_administrator_of_community_with_id(community_id=space_id) and not invite_only:
            raise PermissionDenied(
                _("You cannot create a public appointment if you are not an administrator of a space"),
            )

    def check_can_query_invite_only_appointment(self, user, appointment):
        space_id = appointment.space.id

        if appointment.invite_only and (
            user.is_anonymous or not user.is_member_of_community_with_id(community_id=space_id)
        ):
            raise PermissionDenied(
                _("You cannot query invite only appointments of a space you are not a member of"),
            )

    def check_can_delete_appointment(self, user, appointment):
        space_id = appointment.space.id
        self._check_space_membership(user=user, space_id=space_id, action="delete")

        has_permission = self._check_permission(user, appointment)

        if not has_permission:
            raise PermissionDenied(_("You do not have the permission to delete the appointment"))

    def check_can_update_appointment(self, user, appointment):
        space_id = appointment.space.id
        self._check_space_membership(user=user, space_id=space_id, action="update")

        has_permission = self._check_permission(user, appointment)

        if not has_permission:
            raise PermissionDenied(_("You do not have the permission to update the appointment"))
