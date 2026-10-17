# Example: Django API + React

Django with Django REST framework and JWT login (SimpleJWT) as the backend, and a Vite +
React frontend that uses `kvn-notify-web`. The same setup works for Vue, Svelte or any
other frontend: only the components change.

## Run it

```bash
docker compose up --build
```

Open <http://localhost:5173>, log in as **demo** / **demo**, click **Turn on notifications**,
then **Add a pretend expense**. The push arrives within a few seconds and the item appears in
the inbox list. Vite forwards `/api` to Django, so the browser only ever talks to one origin.

## Without Docker

```bash
# backend
cd backend
pip install -r requirements.txt
python manage.py migrate && python manage.py seed_demo
python manage.py runserver          # terminal 1
python manage.py notify_worker      # terminal 2

# frontend
cd frontend
npm install
npm run dev                         # terminal 3
```

## Where to look

| File | What it shows |
| --- | --- |
| `backend/project/settings.py` | `KVN_NOTIFY` with JWT login through Django REST framework |
| `backend/api/notification_types.py` | A type with push, inbox and an email fallback |
| `backend/api/views.py` | Sending it with `notify()` |
| `frontend/src/notify.js` | Creating the client with a token, registering the service worker |
| `frontend/src/sw.js` | The service worker: two lines |
| `frontend/src/App.jsx` | The on/off button, the inbox, and unsubscribing on logout |
| `frontend/vite.config.js` | Building `sw.js` at the site root |
