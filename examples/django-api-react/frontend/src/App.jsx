import { useCallback, useEffect, useState } from "react";

import { forgetToken, getAccessToken, login } from "./auth.js";
import { notify } from "./notify.js";

const styles = {
  page: { fontFamily: "system-ui, sans-serif", maxWidth: 640, margin: "40px auto", padding: "0 16px" },
  button: { font: "inherit", padding: "8px 16px", borderRadius: 6, border: "1px solid #2563eb", background: "#2563eb", color: "#fff", cursor: "pointer", marginRight: 8 },
  note: { color: "#4b5563", fontSize: 14 },
};

function LoginForm({ onLoggedIn }) {
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await login(form.get("username"), form.get("password"));
      onLoggedIn();
    } catch (exc) {
      setError(exc.message);
    }
  }
  return (
    <form onSubmit={submit}>
      <h1>Log in</h1>
      <p style={styles.note}>Use demo / demo.</p>
      <p><input name="username" placeholder="Username" defaultValue="demo" /></p>
      <p><input name="password" type="password" placeholder="Password" defaultValue="demo" /></p>
      <button style={styles.button} type="submit">Log in</button>
      {error && <p>{error}</p>}
    </form>
  );
}

// --8<-- [start:toggle]
function NotificationToggle() {
  const [subscribed, setSubscribed] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    notify.isSubscribed().then(setSubscribed);
  }, []);

  if (notify.permission() === "unsupported") return <p>This browser does not support notifications.</p>;
  if (notify.permission() === "denied") return <p>Notifications are blocked in your browser settings.</p>;

  async function toggle() {
    setError("");
    try {
      if (subscribed) await notify.unsubscribe();
      else await notify.subscribe(); // asks for permission the first time
      setSubscribed(await notify.isSubscribed());
    } catch (exc) {
      setError(exc.message);
    }
  }

  return (
    <>
      <button style={styles.button} onClick={toggle}>
        {subscribed ? "Turn off notifications" : "Turn on notifications"}
      </button>
      {error && <p>{error}</p>}
    </>
  );
}
// --8<-- [end:toggle]

// --8<-- [start:inbox]
function Inbox({ refreshKey }) {
  const [page, setPage] = useState(null);

  const load = useCallback(() => notify.inbox.list().then(setPage), []);
  useEffect(() => {
    load();
  }, [load, refreshKey]);

  if (!page) return null;
  return (
    <>
      <h2>Inbox ({page.unread_count} unread)</h2>
      <button style={styles.button} onClick={() => notify.inbox.markAllRead().then(load)}>
        Mark all read
      </button>
      <ul>
        {page.results.map((item) => (
          <li key={item.id} style={{ fontWeight: item.read ? 400 : 600 }}>
            {item.title}
          </li>
        ))}
      </ul>
    </>
  );
}
// --8<-- [end:inbox]

export default function App() {
  const [loggedIn, setLoggedIn] = useState(Boolean(getAccessToken()));
  const [sent, setSent] = useState(0);

  useEffect(() => {
    // If this page was opened by tapping a notification, mark it read.
    if (loggedIn) notify.handleOpenedFromPush();
  }, [loggedIn]);

  if (!loggedIn) {
    return (
      <main style={styles.page}>
        <LoginForm onLoggedIn={() => setLoggedIn(true)} />
      </main>
    );
  }

  async function sendDemo() {
    await fetch("/api/demo/send/", { method: "POST", headers: { Authorization: `Bearer ${getAccessToken()}` } });
    setTimeout(() => setSent((n) => n + 1), 500);
  }

  // --8<-- [start:logout]
  async function logout() {
    // Remove this device first, so the next person to log in here gets nothing of yours.
    await notify.unsubscribe().catch(() => {});
    forgetToken();
    setLoggedIn(false);
  }
  // --8<-- [end:logout]

  return (
    <main style={styles.page}>
      <h1>kvn-notify + React</h1>
      <h2>1. Turn notifications on</h2>
      <NotificationToggle />
      <h2>2. Send yourself one</h2>
      <button style={styles.button} onClick={sendDemo}>Add a pretend expense</button>
      <p style={styles.note}>It arrives as a push within a few seconds and appears in the inbox below.</p>
      <Inbox refreshKey={sent} />
      <p><button style={{ ...styles.button, background: "#fff", color: "#2563eb" }} onClick={logout}>Log out</button></p>
    </main>
  );
}
