# Logins, sessions and tokens

**Login only matters for kvn-notify's endpoints: subscribe, unsubscribe, test, preferences and the
inbox.** Sending notifications does not involve login, and the service worker never sees a token.

kvn-notify does not log anyone in. It asks your app who the request belongs to, the same way your
other endpoints do, so it works with whatever login your app already has.

## Which setup should I use?

If you are starting fresh, pick the row that matches your app. They are listed safest first.

| Your app | Recommended login | Why |
| --- | --- | --- |
| Django templates | Django's session cookie. Nothing to configure. | Scripts on the page cannot read the login, and CSRF is built in |
| A frontend (React, Vue, Next.js...) on the **same domain** as the API | Session cookie, e.g. django-allauth headless in "browser" mode | Same safety, no tokens in JavaScript |
| A frontend on a **different domain** from the API | A proxy on the frontend's domain (backend-for-frontend), or header tokens | Browsers increasingly block cookies between unrelated domains |
| A mobile or desktop app | A token in a header, kept in the phone's secure storage | Native apps don't handle cookies and CSRF naturally |

Every one of these, and the other setups below, works with kvn-notify.

## On the server

The `AUTH` setting decides how the endpoints find the user.

| `AUTH` | How the user is found |
| --- | --- |
| `"auto"` (default) | Django REST framework's `DEFAULT_AUTHENTICATION_CLASSES` when DRF is installed, otherwise the session |
| `"drf"` | Always DRF's authentication classes: Simple JWT, `TokenAuthentication`, `SessionAuthentication`, dj-rest-auth, allauth's token class... |
| `"session"` | Django's session cookie (`request.user`) |
| `"myapp.auth.get_user"` | Your function: takes the request, returns a user or `None` |

A custom function covers anything else, for example django-ninja or an API key:

```python
# myapp/auth.py
from myapp.models import ApiKey


def get_user(request):
    key = request.headers.get("X-Api-Key", "")
    api_key = ApiKey.objects.select_related("user").filter(key=key).first()
    return api_key.user if api_key else None
```

```python
KVN_NOTIFY = {
    "AUTH": "myapp.auth.get_user",
    "TOKEN_HEADERS": ["X-Api-Key"],  # see "The CSRF rule" below
}
```

### The CSRF rule

One rule applies in every mode:

> A request that changes something (POST, DELETE) and carries **no token header** must pass
> Django's CSRF check.

The token headers are `Authorization` and `X-Session-Token` (django-allauth's header for apps) by
default; add your own with `TOKEN_HEADERS`.

Why this is safe: a browser attaches cookies to every request to your site, including ones another
site tricks it into sending. A login that arrived without a token header can only have come from a
cookie, so it needs the CSRF check. Nothing attaches a token header by itself, so requests that
carry one can't be forged that way and don't need it. In `"session"` mode the login is always the
cookie, so the check always runs.

You get the protection even if your login library doesn't apply it. For example, dj-rest-auth's
JWT cookie login skips CSRF unless `JWT_AUTH_COOKIE_USE_CSRF` is on; kvn-notify's endpoints check
it anyway.

`ENFORCE_CSRF = False` turns the rule off, with a startup warning
([W010](../troubleshooting.md#w010)). If a token header is why you wanted to, list it in
`TOKEN_HEADERS` instead.

### Tested setups

Every release is tested against each of these:

| Setup | Example |
| --- | --- |
| Django session cookie | Django templates |
| DRF `SessionAuthentication` | A React app with django-allauth headless (browser mode) |
| JWT in an `Authorization` header (Simple JWT) | Tokens held by JavaScript, mobile apps |
| A proxy that turns its own cookie into an `Authorization` header | A Next.js backend-for-frontend |
| DRF `TokenAuthentication` | Scripts, older apps |
| JWT in an HttpOnly cookie (dj-rest-auth) | A frontend on a sibling domain |
| `X-Session-Token` header | django-allauth headless (app mode) |
| A custom function reading a cookie or a header | Anything else |

### Not supported

- **Tokens in the URL** (`?token=...`): they end up in server logs, browser history and the
  `Referer` header. Send them in a header.
- **Login cookies that JavaScript can read**: any script on the page could steal them. kvn-notify
  warns when `SESSION_COOKIE_HTTPONLY` is off in production ([W011](../troubleshooting.md#w011)).
- **Cookies between unrelated domains** (`myapp.com` calling `api-host.io`): browsers block them more
  and more. Use a header token or a proxy. Sibling domains such as `app.example.com` and
  `api.example.com` are fine.

### An extra check: 2FA, staff only

To require more than a login, for example a verified second factor, point `PERMISSION` at a
function that takes the request and the user:

```python
# myapp/notify_access.py
def verified_only(request, user):
    return user.is_verified()  # django-otp


KVN_NOTIFY = {"PERMISSION": "myapp.notify_access.verified_only", ...}
```

A user who fails it gets `403` from every endpoint. It is also the place to refuse impersonated
sessions (for example `return not getattr(request.user, "is_hijacked", False)` with django-hijack),
so an admin acting as someone doesn't register their own browser to that person.

## In the browser

Tell the client how to authenticate once, when you create it. The service worker needs nothing:
it only shows what arrives.

=== "Session cookie"

    ```javascript
    import { createClient } from "kvn-notify-web";

    const notify = createClient({ baseUrl: "/notify" });
    ```

    The client reads Django's `csrftoken` cookie and sends it as `X-CSRFToken` on every change.
    If you renamed the cookie (`CSRF_COOKIE_NAME`), pass `csrfCookieName`. With
    `CSRF_COOKIE_HTTPONLY = True` the cookie cannot be read, so the client looks for a
    `<meta name="csrf-token">` tag or a `csrfmiddlewaretoken` form field on the page instead
    (`{% kvn_notify_scripts %}` passes the token for you), or pass `csrfToken`.

=== "Cookie, API on a sibling domain"

    ```javascript
    const notify = createClient({
      baseUrl: "https://api.example.com/notify",
      credentials: "include",
    });
    ```

    The server needs CORS with credentials allowed (django-cors-headers:
    `CORS_ALLOW_CREDENTIALS = True`) and the frontend's address in `CSRF_TRUSTED_ORIGINS`. The page
    can only read the `csrftoken` cookie if Django sets it for the shared parent domain
    (`CSRF_COOKIE_DOMAIN = ".example.com"`); otherwise pass `csrfToken`.

=== "Token in a header"

    ```javascript
    const notify = createClient({
      baseUrl: "/api/notify",
      getHeaders: async () => ({ Authorization: `Bearer ${await getAccessToken()}` }),
      // When a token has expired: refresh it, and the request is retried once.
      onUnauthorized: async () => refreshAccessToken(), // return true if it worked
    });
    ```

    `getHeaders` runs before every request, so a refreshed token is always used. Requests with a
    token header carry no CSRF token. For another header name, pass `tokenHeaders` (and list it in
    the server's `TOKEN_HEADERS`).

=== "Proxy (backend-for-frontend)"

    ```javascript
    const notify = createClient({ baseUrl: "/api/proxy/notify" });
    ```

    Your proxy route forwards the request to Django and adds the token, so the browser code
    configures nothing else. Protect the proxy's own cookie as you would any session (`SameSite`,
    and an `Origin` check on changing requests).

=== "Django templates"

    Nothing to configure. `{% kvn_notify_scripts %}` creates a session client pointing at the
    right URL and exposes it as `window.kvnNotify.client`.

Apps that don't use kvn-notify's endpoints at all can still use the browser part; see
[Using your own endpoints](own-endpoints.md).

## Logout, password changes, "log out everywhere"

A push subscription belongs to the browser, not to the login. If one person logs out and another
logs in on the same device without removing it, the first person's notifications keep arriving.

Three things prevent that:

1. **Your frontend removes the device before logging out:**

    ```javascript
    await notify.unsubscribe();   // or window.kvnNotify.unsubscribe() in template projects
    ```

    Call it while the user is still logged in, because the server must know whose device it is.

2. **The server moves a device to whoever subscribes it.** If a device registered by one user is
   subscribed again while another user is logged in, it now belongs to the new user only. The same
   applies to apps that let one browser switch between several accounts: the device follows the
   account that last turned notifications on.

3. **A password change removes all of the user's devices**, just as Django ends their other
   sessions. A stolen or old phone stops receiving notifications; the user turns them on again on
   the devices they still use. Turn this off with `REMOVE_DEVICES_ON_PASSWORD_CHANGE = False`.
   For a "log out of all devices" button, call `kvn_notify.remove_devices(user)` yourself.
