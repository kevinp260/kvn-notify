"""Signals sent by the dispatcher, so apps can react to what happened.

    from django.dispatch import receiver
    from kvn_notify.signals import delivery_sent

    @receiver(delivery_sent)
    def remember_alert_time(sender, delivery, **kwargs):
        notification = delivery.notification
        ...

Receivers run in the dispatcher after the delivery is recorded. An exception in a
receiver is logged and never undoes or repeats the delivery.
"""

from django.dispatch import Signal

# A delivery reached its channel: the push service accepted it, the mail server took it.
# Arguments: delivery
delivery_sent = Signal()

# A delivery failed for good (no more retries).
# Arguments: delivery, error
delivery_failed = Signal()
