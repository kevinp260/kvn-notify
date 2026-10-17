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
