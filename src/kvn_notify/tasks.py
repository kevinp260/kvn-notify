"""Celery tasks, used when KVN_NOTIFY["DISPATCH"] == "celery".

Add a periodic task so retries and anything queued while the broker was down get sent:

    CELERY_BEAT_SCHEDULE = {
        "kvn-notify-sweep": {"task": "kvn_notify.process_due", "schedule": 60.0},
        "kvn-notify-cleanup": {"task": "kvn_notify.cleanup", "schedule": 3600.0},
    }
"""

from celery import shared_task

from kvn_notify import dispatch


@shared_task(name="kvn_notify.send_deliveries", ignore_result=True)
def send_deliveries(delivery_ids):
    dispatch.send_now(list(delivery_ids))


@shared_task(name="kvn_notify.process_due", ignore_result=True)
def process_due():
    dispatch.process_due()


@shared_task(name="kvn_notify.cleanup", ignore_result=True)
def cleanup():
    dispatch.cleanup()
