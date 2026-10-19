from django.apps import AppConfig


class KvnNotifyConfig(AppConfig):
    name = "kvn_notify"
    verbose_name = "Notifications"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from django.utils.module_loading import autodiscover_modules

        from kvn_notify import checks, handlers  # noqa: F401  registers the startup checks

        handlers.connect()
        from kvn_notify.channels import register_builtin_channels
        from kvn_notify.types import NotificationType, register

        register_builtin_channels()
        register(
            NotificationType(
                key="kvn_notify.test",
                channels=("push",),
                required=True,
                title="Notifications are working",
                body="This device will receive notifications from now on.",
                url="/",
                tag="kvn-notify-test",
                ttl=300,
            )
        )
        # Each app declares its types in a notification_types.py module.
        autodiscover_modules("notification_types")
