# Deploying and moving an existing app

## Before you go live

- [ ] **HTTPS.** Browsers only allow push on secure pages. `localhost` counts as secure; a LAN
  address like `192.168.1.10` does not.
- [ ] **VAPID keys are stored as secrets** and backed up. Losing or changing them stops every
  subscribed device.
- [ ] **`VAPID_SUBJECT`** is a real `mailto:` address or your site's URL. Push services use it to
  contact you about problems.
- [ ] **`SITE_URL`** is your public address, so email links work.
- [ ] **The dispatcher runs** as a service next to the web process. See
  [Running the dispatcher](dispatch.md).
- [ ] **`python manage.py check --deploy`** shows no `kvn_notify` warnings.
- [ ] **The service worker is served from the site root** (`/sw.js`), with no long cache. Browsers
  check it for updates, and a cached old worker keeps old behaviour.

## iPhones and iPads

Web Push works on iOS and iPadOS 16.4 and newer, but only for sites the user has **added to the
home screen**. In Safari tabs, `kvnNotify.permission()` reports `"unsupported"` until then.

To make that possible your site needs a web app manifest with `"display": "standalone"`, a name
and icons. Consider showing iPhone users a short hint to use **Share → Add to Home Screen**.

## Moving an app that already sends push

If your app already has its own push code, its users have subscribed devices. You can move those
devices to kvn-notify so nobody has to turn notifications on again.

**Keep your existing VAPID keys.** Put them in `KVN_NOTIFY`. The devices were subscribed with
those keys and only accept messages signed with them.

Then copy the devices with a data migration in one of your apps. Adjust the old model's name and
fields:

```python
# yourapp/migrations/00xx_move_push_devices_to_kvn_notify.py
import hashlib

from django.db import migrations


def copy_devices(apps, schema_editor):
    OldSubscription = apps.get_model("yourapp", "PushSubscription")
    NewSubscription = apps.get_model("kvn_notify", "PushSubscription")
    for old in OldSubscription.objects.filter(is_active=True).iterator():
        NewSubscription.objects.update_or_create(
            endpoint_hash=hashlib.sha256(old.endpoint.encode()).hexdigest(),
            defaults={
                "user_id": old.user_id,
                "endpoint": old.endpoint,
                "p256dh": old.p256dh,
                "auth": old.auth,
                "active": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("yourapp", "00xx_previous"),
        ("kvn_notify", "0001_initial"),
    ]
    operations = [migrations.RunPython(copy_devices, migrations.RunPython.noop)]
```

Historical models in migrations do not run the model's `save()`, which is why the migration sets
`endpoint_hash` itself.

Then:

1. Replace your push calls with `notify()` and your service worker's push code with kvn-notify's.
2. Point your frontend's subscribe button at kvn-notify's endpoints.
3. Keep the old tables until you have confirmed in production that notifications arrive, then
   remove them in a later release.

## Database

PostgreSQL or MySQL is recommended. Several dispatchers can then run side by side, because each
delivery is locked while it is sent. SQLite works with a single dispatcher.

Old records are deleted after `DELIVERY_RETENTION_DAYS` (90), and inbox items after
`INBOX_RETENTION_DAYS` (90). Set either to `0` to keep everything.
