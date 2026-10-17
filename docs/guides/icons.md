# Icons and badges

**A push notification uses two images, and the small one only works as a white symbol on a
transparent background.** Most "white square" problems come from using the app icon as the badge.

| Image | Where it shows | What it must be |
| --- | --- | --- |
| `ICON` | Inside the open notification | Full colour is fine. At least 192×192. |
| `BADGE` | The phone's status bar, at the top of the screen | A **white symbol on a transparent background**, 96×96 |

Android ignores the badge's colours and uses only its transparency: every pixel that is not
transparent is drawn white. So:

- an image with **no transparency** shows as a solid white square;
- a **full app icon** with transparent corners shows as a white blob in the shape of the icon;
- a **symbol on transparency** shows as that symbol, as intended.

When no badge is set at all, Chrome shows its default bell.

## Setting them

```python
KVN_NOTIFY = {
    "BADGE": "icons/badge-96.png",  # a static path...
    "ICON": "icons/icon-192.png",
    # ...or a URL, when the frontend serves the files: "/badge-96.png"
}
```

The service worker always uses these two settings, so individual notifications cannot use a wrong
badge by accident.

## Making a badge from your logo

```bash
pip install "kvn-notify[icons]"
python manage.py notify_make_badge static/logo.png
```

It writes `static/logo-badge-96.png`: your logo's shape in white, centred on a transparent 96×96
square. A PNG with transparency gives the best result. For a logo on a solid background, the
command takes the colour in the corners as the background and keeps everything that differs from
it; adjust with `--threshold` (0–255) if too much or too little is kept.

Simple shapes work best at status bar size: a bold letter or a plain outline, not a detailed
illustration.

## The startup checks

`python manage.py check`, which also runs before `runserver` and `migrate`, opens your images and
warns about:

| Check | Problem |
| --- | --- |
| [W002](../troubleshooting.md#w002) | No badge is set |
| [W003](../troubleshooting.md#w003) | The badge has no transparency: white square |
| [W004](../troubleshooting.md#w004) | The badge is mostly solid, like an app icon: white blob |
| [W005](../troubleshooting.md#w005) | The badge is smaller than 72×72 |
| [W006](../troubleshooting.md#w006) | The file is not in your static files |
| [W007](../troubleshooting.md#w007) | The icon is smaller than 192×192 |

Images given as URLs are not checked, because they may not exist until the frontend is built.

To fail a CI run or deploy on these instead of warning, set `"STRICT_ICONS": True`.

## The colour of the notification

The accent colour Android uses for the small icon in the open notification shade comes from the
browser and your web app manifest's `theme_color`, not from kvn-notify. Set `theme_color` in your
manifest to your brand colour.
