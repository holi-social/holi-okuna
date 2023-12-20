from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError


class AppointmentChecker:
    def check_can_create_appointment(self, user, invite_only, space_id):
        if not user.is_member_of_community_with_id(community_id=space_id):
            raise ValidationError(
                _("You cannot create an appointment for a space you are not a member of"),
            )

        if not user.is_administrator_of_community_with_id(community_id=space_id) and not invite_only:
            raise ValidationError(
                _("You cannot create a public appointment if you are not an administrator of a space"),
            )

    def check_can_query_invite_only_appointment(self, user, appointment):
        space_id = appointment.space.id

        if appointment.invite_only and (user.is_anonymous or not user.is_member_of_community_with_id(space_id)):
            raise ValidationError(
                _("You cannot query invite only appointments of a space you are not a member of"),
            )
