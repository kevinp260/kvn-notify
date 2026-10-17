# Logins, sessions and tokens

**Login only matters for kvn-notify's endpoints: subscribe, unsubscribe, test, preferences and the
inbox.** Sending notifications does not involve login, and the service worker never sees a token.

## On the server

The `AUTH` setting decides how the endpoints find the user.

| `AUTH` | How the user is found | CSRF |
| --- | --- | --- |
| `"auto"` (default) | Django REST framework's `DEFAULT_AUTHENTICATION_CLASSES` when DRF is installed, otherwise the session | As below for each |
| `"drf"` | Always DRF's authentication classes: SimpleJWT, `TokenAuthentication`, `SessionAuthentication`, ... | Enforced by DRF's `SessionAuthentication`; not needed for tokens |
| `"session"` | Django's session cookie (`request.user`) | Enforced on POST and DELETE |
| `"myapp.auth.get_user"` | Your function: takes the request, returns a user or `None` | Your function's job |

A custom function covers anything else, for example django-ninja or a header from a gateway:

```python
# myapp/auth.py
from myapp.models import ApiKey


def get_user(request):
    key = request.headers.get("X-Api-Key", "")
    api_key = ApiKey.objects.select_related("user").filter(key=key).first()
    return api_key.user if api_key else None
```

### An extra check: 2FA, staff only

To require more than a login, for example a verified second factor, point `PERMISSION` at a
function that takes the request and the user:

```python
# myapp/notify_access.py
def verified_only(request, user):
    return user.is_verified()  # django-otp


KVN_NOTIFY = {"PERMISSION": "myapp.notify_access.verified_only", ...}
```

A user who fails it gets `403` from every endpoint.

## In the browser

Tell the client how to authenticate once, when you create it.

=== "Session cookie"

    ```javascript
    import { createClient } from "kvn-notify-web";

    const notify = createClient({ baseUrl: "/notify" });
    ```

    The client reads Django's `csrftoken` cookie and sends it as `X-CSRFToken` on every change.
    If you renamed the cookie (`CSRF_COOKIE_NAME`), pass `csrfCookieName`. With
    `CSRF_COOKIE_HTTPONLY = True` the cookie cannot be read, so the client looks for a
    `<meta name="csrf-token">` tag or a `csrfmiddlewaretoken` form field on the page
    instead (`{% kvn_notify_scripts %}` passes the token for you), or pass `csrfToken`. For an API on another
    origin, add `credentials: "include"` and configure CORS and `CSRF_TRUSTED_ORIGINS`.

=== "Token (JWT and others)"

    ```javascript
    import { createClient } from "kvn-notify-web";

    const notify = createClient({
      baseUrl: "/api/notify",
      getHeaders: async () => ({ Authorization: `Bearer ${await getAccessToken()}` }),
    });
    ```

    `getHeaders` runs before every request, so a refreshed token is always used. When an
    `Authorization` header is present, no CSRF token is sent.

=== "Django templates"

    Nothing to configure. `{% kvn_notify_scripts %}` creates a session client pointing at the
    right URL and exposes it as `window.kvnNotify.client`.

## Logout

A push subscription belongs to the browser, not to the login. If one person logs out and another
logs in on the same device without removing it, the first person's notifications keep arriving.

Two things prevent that:

1. **Your frontend removes the device before logging out:**

    ```javascript
    await notify.unsubscribe();   // or window.kvnNotify.unsubscribe() in template projects
    ```

    Call it while the user is still logged in, because the server must know whose device it is.

2. **The server moves a device to whoever subscribes it.** If a device registered by one user is
   subscribed again while another user is logged in, it now belongs to the new user only.
