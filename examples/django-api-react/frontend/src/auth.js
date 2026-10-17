// Minimal JWT handling for the example. Real apps refresh tokens and handle expiry.
const KEY = "demo-access-token";

export function getAccessToken() {
  try {
    return localStorage.getItem(KEY) || "";
  } catch {
    return "";
  }
}

export async function login(username, password) {
  const response = await fetch("/api/token/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) throw new Error("Wrong username or password.");
  const { access } = await response.json();
  localStorage.setItem(KEY, access);
}

export function forgetToken() {
  localStorage.removeItem(KEY);
}
