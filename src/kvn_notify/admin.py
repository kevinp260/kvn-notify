from django.contrib import admin

from kvn_notify.models import Delivery, Notification, Preference, PushSubscription


class DeliveryInline(admin.TabularInline):
    model = Delivery
    extra = 0
    can_delete = False
    fields = ("channel", "status", "attempts", "is_fallback", "next_attempt_at", "sent_at", "last_error")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("type", "recipient_label", "title", "in_inbox", "read_at", "created_at")
    list_filter = ("type", "in_inbox")
    search_fields = ("type", "title", "email", "dedupe_key")
    readonly_fields = ("id", "recipient_key", "created_at")
    raw_id_fields = ("user",)
    inlines = [DeliveryInline]
    date_hierarchy = "created_at"


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "notification",
        "channel",
        "status",
        "attempts",
        "is_fallback",
        "next_attempt_at",
        "sent_at",
    )
    list_filter = ("status", "channel", "is_fallback")
    search_fields = ("last_error", "notification__type")
    raw_id_fields = ("notification", "subscription")
    readonly_fields = ("created_at", "updated_at")
    actions = ["retry_now"]

    @admin.action(description="Retry the selected deliveries now")
    def retry_now(self, request, queryset):
        from django.utils import timezone

        count = queryset.exclude(status=Delivery.Status.SENT).update(
            status=Delivery.Status.PENDING, next_attempt_at=timezone.now(), attempts=0, claimed_at=None
        )
        self.message_user(request, f"{count} deliveries queued again.")


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "active", "user_agent", "last_success_at", "created_at")
    list_filter = ("active",)
    search_fields = ("user_agent", "disabled_reason")
    raw_id_fields = ("user",)
    readonly_fields = ("endpoint_hash", "created_at", "updated_at", "last_success_at", "disabled_at")


@admin.register(Preference)
class PreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "channel", "enabled", "updated_at")
    list_filter = ("channel", "enabled")
    raw_id_fields = ("user",)
