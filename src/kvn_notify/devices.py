"""Short, readable device names from a browser's user agent string.

    "Mozilla/5.0 (Linux; Android 10; K) ... Chrome/141.0 Mobile Safari/537.36"
    -> "Chrome on Android"

No library and no guessing beyond the common browsers: anything unrecognised
becomes "Browser on <system>" or just "Browser".
"""

from __future__ import annotations

# Order matters: many browsers also mention "Chrome" or "Safari" in their string.
_BROWSERS = (
    ("EdgA/", "Edge"),
    ("EdgiOS/", "Edge"),
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("Opera", "Opera"),
    ("SamsungBrowser/", "Samsung Internet"),
    ("Brave", "Brave"),
    ("Vivaldi/", "Vivaldi"),
    ("YaBrowser/", "Yandex Browser"),
    ("FxiOS/", "Firefox"),
    ("Firefox/", "Firefox"),
    ("CriOS/", "Chrome"),
    ("Chrome/", "Chrome"),
    ("Chromium/", "Chromium"),
    ("Safari/", "Safari"),
)

_SYSTEMS = (
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("CrOS", "ChromeOS"),
    ("Windows", "Windows"),
    ("Macintosh", "macOS"),
    ("Mac OS X", "macOS"),
    ("Linux", "Linux"),
)


def describe_user_agent(user_agent: str) -> str:
    user_agent = user_agent or ""
    browser = next((name for marker, name in _BROWSERS if marker in user_agent), "")
    system = next((name for marker, name in _SYSTEMS if marker in user_agent), "")
    if browser and system:
        return f"{browser} on {system}"
    if system:
        return f"Browser on {system}"
    return browser or "Browser"
