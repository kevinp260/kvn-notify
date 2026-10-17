from kvn_notify import NotificationType, register

register(
    NotificationType(
        key="demo.expense_added",
        channels=["push", "inbox"],
        fallback="email",  # users with no device get an email instead
        title="{who} added {amount}",
        body="In {group}. Tap to see the balance.",
        url="/",
        description="When someone adds an expense to one of your groups",
    )
)
