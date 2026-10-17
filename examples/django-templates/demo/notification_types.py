# --8<-- [start:types]
from kvn_notify import NotificationType, register

register(
    NotificationType(
        key="demo.order_shipped",
        channels=["push", "email", "inbox"],
        title="Order {order_number} is on its way",
        body="It left the warehouse and should arrive {arrival}.",
        url="/inbox/",
        description="When one of your orders ships",
    )
)
# --8<-- [end:types]
