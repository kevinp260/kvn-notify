# Troubleshooting

Start with `python manage.py check`. It finds most setup problems, and each message links to its
entry below. To see what happened to a specific notification, open it in the Django admin under
**Notifications**: every delivery shows its status, attempts and last error.

## Common problems

### The badge shows as a white square or a bell {#white-square}

The status bar badge must be a white symbol on a transparent background. An image without
transparency becomes a white square; a missing badge shows the browser's bell. See
[W002](#w002), [W003](#w003) and [Icons and badges](guides/icons.md).

### The browser never asks for permission {#no-prompt}

- `subscribe()` must run from a click or tap. Called on page load, browsers ignore it.
- The user may have blocked notifications for your site: `permission()` returns `"denied"`. Only
  the user can undo this, in the browser's site settings.
- The page must be secure: `https://`, or `localhost` during development.

### "No service worker controls this page" {#no-service-worker}

`subscribe()` waited `readyTimeout` for a service worker and none covered the page. Check that:

- the page registers one (`navigator.serviceWorker.register("/sw.js")`);
- it is served from the **site root**: a worker at `/static/sw.js` only covers pages under
  `/static/`;
- it loads without errors (browser dev tools → Application → Service workers).

Or use the package's ready-made worker: `{% kvn_notify_scripts "default" %}`, or
`createClient({ serviceWorker: "/notify/sw.js" })`.

### Nothing arrives on an iPhone {#iphone}

Web Push on iOS and iPadOS needs version 16.4 or newer, and works only after the user adds your
site to the home screen and opens it from there. See [Deploying](guides/deploying.md#iphones-and-ipads).
`client.needsInstall()` tells you when to show that hint.

### Subscribing fails with 403 {#csrf}

Any login without a token header needs Django's CSRF token, including custom functions and JWTs
in cookies ([the CSRF rule](guides/login.md#the-csrf-rule)). The client sends it from the
`csrftoken` cookie; if you renamed the cookie, pass `csrfCookieName`. If the frontend is on
another origin, add it to `CSRF_TRUSTED_ORIGINS` and use `credentials: "include"`. If your login
uses its own header (an API key, say), list it in `TOKEN_HEADERS` on the server and `tokenHeaders`
in the client.

### Subscribing fails with 401 {#unauthorized}

The endpoints did not find a logged-in user. With tokens, check that `getHeaders` returns the
`Authorization` header and that the token is still valid; `onUnauthorized` can refresh an expired
one and retry. With `AUTH: "auto"` and Django REST
framework installed, your `DEFAULT_AUTHENTICATION_CLASSES` decide who is logged in; see
[Logins](guides/login.md).

### Notifications are saved but never sent {#not-sent}

No dispatcher is running. Deliveries stay **pending** in the admin. Start
`python manage.py notify_worker`, or check your Celery beat schedule. See
[Running the dispatcher](guides/dispatch.md).

### Every device stopped receiving {#keys-changed}

The VAPID keys changed. Devices are tied to the keys they subscribed with, and the push service
rejects messages signed with other keys (deliveries fail with 401 or 403 and "check the VAPID
keys"). Put the old keys back, or ask users to turn notifications on again.

### Emails go to spam {#spam}

Usually the sending domain is not set up: add SPF and DKIM records for the domain in
`EMAIL["FROM"]`, as your email provider describes. A real sender address and `SITE_URL` links on
your own domain also help.

### Emails have no button {#no-button}

`SITE_URL` is not set, so relative links cannot become full addresses. See [W009](#w009).

## Startup check codes

### E001: invalid `DISPATCH` {#e001}

`DISPATCH` must be `"worker"`, `"celery"` or `"inline"`.

### E002: Celery is not installed {#e002}

`DISPATCH` is `"celery"`: run `pip install "kvn-notify[celery]"`, or choose another mode.

### E003: Django REST framework is not installed {#e003}

`AUTH` is `"drf"`: run `pip install "kvn-notify[drf]"`, or set `AUTH` to `"session"`.

### E004: unknown channel {#e004}

A notification type names a channel that does not exist. Check the spelling (`"push"`, `"email"`,
`"inbox"`), or register your own channel; see [Adding a channel](guides/custom-channels.md).

### E005: a custom function cannot be imported {#e005}

`AUTH` or `PERMISSION` names a function by its dotted path, e.g. `"myapp.auth.get_user"`, and
that path does not import. Check the spelling, and that the module is in an installed app or on the
Python path.

### W001: Web Push is not configured {#w001}

`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` or `VAPID_SUBJECT` is empty. Run
`python manage.py notify_vapid_keys`, store the output as secrets and set `VAPID_SUBJECT` to
`"mailto:you@example.com"`.

### W002: no push badge {#w002}

Phones show the browser's default icon instead of yours. Set `BADGE` to a 96×96 white symbol on a
transparent background. `python manage.py notify_make_badge logo.png` makes one.

### W003: badge has no transparency {#w003}

Android draws every non-transparent pixel of the badge white, so an image with no transparency is
a white square. Use a white symbol on a transparent background, or run `notify_make_badge` on your
logo.

### W004: badge is mostly solid {#w004}

The badge looks like a full app icon. Android shows it as a white blob in the icon's shape. Use
just the symbol, on transparency.

### W005: badge is too small {#w005}

Use 96×96. Smaller images look blurry on high-resolution screens.

### W006: image not found {#w006}

The `BADGE` or `ICON` path is not in your static files. Static paths are relative to a static
folder, e.g. `"icons/badge-96.png"` for `yourapp/static/icons/badge-96.png`. Use a URL starting
with `/` or `https://` for files served elsewhere.

### W007: icon is too small {#w007}

Use at least 192×192 for `ICON`.

### W008: inbox type but `INBOX` is off {#w008}

A type includes the `"inbox"` channel, but nothing is stored until you set `"INBOX": True`.

### W009: `SITE_URL` is empty {#w009}

Emails cannot turn relative links into full addresses, so they are sent without a button. Set
`SITE_URL` to your public address, e.g. `"https://app.example.com"`.

### W010: `ENFORCE_CSRF` is off {#w010}

The endpoints accept changing requests whose login came from a cookie without checking CSRF, so
another website could make a logged-in visitor's browser subscribe or change preferences. If you
turned it off because your login uses its own header, list that header in `TOKEN_HEADERS` and
remove `ENFORCE_CSRF`. See [The CSRF rule](guides/login.md#the-csrf-rule).

### W011: the session cookie is readable by scripts {#w011}

`SESSION_COOKIE_HTTPONLY` is `False` in production, so any script on your pages, including one
injected through a bug, can read the login cookie and take over the session. Remove the setting
(Django's default is `True`).
