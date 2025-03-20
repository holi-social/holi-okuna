from django.contrib import admin, messages
from django.contrib.admin import BooleanFieldListFilter
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils import timezone
from django.utils.translation import ngettext
from rangefilter.filters import DateRangeQuickSelectListFilterBuilder

from openbook_appointments.models import Appointment


@admin.register(Appointment)
class AppointmentAdminModel(admin.ModelAdmin):
    model = Appointment
    actions = ["restore_deleted"]

    @admin.display(description="Space")
    def space_name(self, obj: Appointment) -> str:
        return obj.space.title

    list_display = (
        "id",
        "space_name",
        "title",
        "created",
        "creator",
        "is_deleted",
        "deleted_at",
    )

    list_filter = (
        ("created", DateRangeQuickSelectListFilterBuilder()),
        ("is_deleted", BooleanFieldListFilter),
        ("deleted_at", DateRangeQuickSelectListFilterBuilder()),
    )
    search_fields = (
        "title",
        "space_name",
    )

    exclude = ["geolocation_geojson"]

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet) -> None:
        queryset.filter(is_deleted=False).update(is_deleted=True, deleted_at=timezone.now())

    @admin.action(description="Un-delete selected appointments")
    def restore_deleted(self, request: HttpRequest, queryset: QuerySet) -> None:
        amount_restored = queryset.filter(is_deleted=True).update(is_deleted=False, deleted_at=None)
        self.message_user(
            request,
            ngettext(
                "{} appointment was restored from deletion",
                "{} appointments were restored from deletion",
                amount_restored,
            ).format(amount_restored),
            messages.SUCCESS,
        )
