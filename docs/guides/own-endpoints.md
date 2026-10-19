# Using your own endpoints

kvn-notify's endpoints (`kvn_notify.urls`) cover most apps. If you'd rather keep everything in
your own API, with your own URLs, serializers, permissions and login, use the same functions they
use. Nothing in kvn-notify needs its endpoints to be installed.

## On the server

```python
# myapp/views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response

from kvn_notify import inbox, register_device, remove_device, send_test


@api_view(["POST"])
def save_device(request):
    try:
        device, created = register_device(
            request.user,
            request.data,  # the browser's subscription JSON
            user_agent=request.headers.get("User-Agent", ""),
        )
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    return Response({"id": device.pk, "name": device.label}, status=201 if created else 200)


@api_view(["POST"])
def forget_device(request):
    remove_device(request.user, request.data.get("endpoint", ""))
    return Response(status=204)


@api_view(["GET"])
def my_inbox(request):
    items = inbox.inbox_items(request.user)[:20]
    return Response({"results": [inbox.serialize(n) for n in items]})
```

| Function | Does |
| --- | --- |
| `register_device(user, subscription, user_agent="", device_name="")` | Saves a browser's subscription, or moves a known one to `user`. Raises `ValueError` for anything malformed or unsafe. |
| `remove_device(user, endpoint)` | Forgets one device of `user`. |
| `remove_devices(user)` | Forgets all of them ("log out everywhere"). |
| `list_devices(user)` | For a "your devices" page; show `device.label`. |
| `send_test(user)` | Pushes "Notifications are working" to every device. |
| `get_preferences(user)`, `set_preference(user, type, channel, enabled)` | A settings screen. |
| `inbox.inbox_items`, `unread_count`, `mark_read`, `mark_all_read`, `serialize` | The in-app inbox. |

Your views decide who the user is, so the CSRF rule in the [login guide](login.md) doesn't apply
to them: protect them as you protect the rest of your API.

You still need to serve the VAPID public key to the browser, from `settings.KVN_NOTIFY` or
`kvn_notify.conf.notify_settings.VAPID_PUBLIC_KEY`.

## In the browser

`createBrowserSubscription()` does the browser half on its own: it asks permission (call it from a
click), subscribes this browser, and gives you the JSON to send to your endpoint.

```javascript
import { createBrowserSubscription, removeBrowserSubscription, needsInstall } from "kvn-notify-web";

async function turnOn() {
  if (needsInstall()) return showHint("Add this site to your Home Screen first.");
  const subscription = await createBrowserSubscription({ vapidPublicKey: VAPID_KEY });
  await api.post("/me/devices/", subscription);
}

async function turnOff() {
  const endpoint = await removeBrowserSubscription();
  if (endpoint) await api.post("/me/devices/forget/", { endpoint });
}
```

The service worker part (`kvn-notify-web/sw`) is the same either way: it shows what kvn-notify
sends, whichever endpoint saved the device.
