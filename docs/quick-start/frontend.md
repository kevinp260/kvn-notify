# Quick start: Django API + any frontend

This guide is for projects where Django serves an API and a separate frontend (React, Vue,
Svelte, Angular, plain JavaScript) renders the pages. The code comes from the
[`examples/django-api-react`](https://github.com/kevinp260/kvn-notify/tree/main/examples/django-api-react)
project, which uses Django REST framework with JWT login and a Vite + React frontend. Run it with
`docker compose up --build`.

Only the components are React-specific. The client and service worker code are plain JavaScript.

## Backend

### 1. Install the package

```bash
pip install "kvn-notify[drf]"
```

The `drf` extra makes sure Django REST framework is installed, so the endpoints can use the
login your API already has.

### 2. Create your VAPID keys

```bash
python manage.py notify_vapid_keys
```

Store both values as secrets. Create them **once**: devices are tied to these keys, and changing
them later silently stops every existing device.

### 3. Settings

Add `"kvn_notify"` to `INSTALLED_APPS`, then:

```python
--8<-- "examples/django-api-react/backend/project/settings.py:kvn_notify"
```

The example logs in with JWT through Django REST framework:

```python
--8<-- "examples/django-api-react/backend/project/settings.py:drf"
```

With `AUTH: "auto"`, kvn-notify's endpoints use your `DEFAULT_AUTHENTICATION_CLASSES`. JWT,
`TokenAuthentication` and `SessionAuthentication` all work with no extra code. See
[Logins, sessions and tokens](../guides/login.md) for other setups.

`BADGE` and `ICON` are URLs here because the frontend serves them. They must be absolute paths
on the site the user sees (`/badge-96.png`), or full URLs.

### 4. URLs and tables

```python
urlpatterns = [
    # ...
    path("api/notify/", include("kvn_notify.urls")),
]
```

```bash
python manage.py migrate
python manage.py check
```

### 5. Declare a type and send it

```python
--8<-- "examples/django-api-react/backend/api/notification_types.py"
```

```python
--8<-- "examples/django-api-react/backend/api/views.py"
```

### 6. Start the dispatcher

```bash
python manage.py notify_worker
```

## Frontend

### 7. Install the client

```bash
npm install kvn-notify-web
```

It has no dependencies and ships its own TypeScript types.

### 8. Create the client

Create it once and import it wherever you need it. With a token login, pass a function that
returns the header:

```javascript
--8<-- "examples/django-api-react/frontend/src/notify.js:client"
```

With a session login (cookies), leave `getHeaders` out. The client then sends Django's CSRF token
for you:

```javascript
export const notify = createClient({ baseUrl: "/api/notify" });
```

`baseUrl` is where you included `kvn_notify.urls`. If the API is on another origin, also pass
`credentials: "include"` for sessions, and allow that origin in your CORS settings. Not sure which
login suits your app, or using a proxy? See [Which setup should I use?](../guides/login.md#which-setup-should-i-use).

On iPhones and iPads push only works once the site is on the Home Screen: check
`notify.needsInstall()` and show that hint instead of the button.

### 9. The service worker

The worker shows notifications and opens the link when one is tapped. Two lines:

```javascript
--8<-- "examples/django-api-react/frontend/src/sw.js:sw"
```

It must be served from your site root (`/sw.js`), so it covers every page. The example builds it
with Vite as a second entry:

```javascript
--8<-- "examples/django-api-react/frontend/vite.config.js"
```

And registers it when the app starts:

```javascript
--8<-- "examples/django-api-react/frontend/src/notify.js:register"
```

!!! note "Already using a service worker?"

    With Workbox, `vite-plugin-pwa` or your own worker, add the two lines to that worker
    instead. One worker per site is the rule.

### 10. The on/off button

`subscribe()` must run from a click: browsers only show the permission prompt in response to one.

```jsx
--8<-- "examples/django-api-react/frontend/src/App.jsx:toggle"
```

**Try it:** log in, click the button and allow notifications. Then call your send endpoint. The
notification arrives within a few seconds.

### 11. Remove the device on logout

A device belongs to the browser, not the login. Remove it before you forget the token:

```javascript
--8<-- "examples/django-api-react/frontend/src/App.jsx:logout"
```

## Next steps

- [The in-app inbox](../guides/inbox.md): the example's inbox list uses it.
- [JavaScript reference](../reference/javascript.md): every function of the client.
- [Deploying](../guides/deploying.md): HTTPS, iPhones, and moving an app that already sends push.
- Something not working? [Troubleshooting](../troubleshooting.md).
