from kvn_notify import NotificationType, register

register(
    NotificationType(
        key="leave.approved",
        channels=["email", "push"],
        title="Your leave request was approved",
        body="{leave_type}, {dates}",
        url="/leaves/{leave_id}",
        description="When a manager approves your leave",
    )
)

register(
    NotificationType(
        key="monitor.down",
        channels=["push"],
        fallback="email",
        required=True,
        title="[DOWN] {name}",
        body="{cause}",
        url="/monitors/{monitor_id}",
        tag="incident-{incident_id}",
        urgency="high",
    )
)

register(
    NotificationType(
        key="group.expense",
        channels=["push", "inbox"],
        title="{who} added {amount}",
        url="/groups/1",
    )
)

register(
    NotificationType(
        key="leave.custom_email",
        channels=["email"],
        title="Custom",
        email_template="testapp/email/custom",
    )
)

register(
    NotificationType(
        key="alert.group",
        channels=["push"],
        required=True,
        title="[DOWN] {name}",
        tag="incident-{incident_id}",
    )
)

register(
    NotificationType(
        key="i18n.check",
        channels=["push", "email"],
        # Callables see the language that is active while this recipient's copy renders.
        title=lambda context: (
            f"title in {__import__('django.utils.translation').utils.translation.get_language()}"
        ),
        email_subject=lambda context: (
            f"subject in {__import__('django.utils.translation').utils.translation.get_language()}"
        ),
    )
)
