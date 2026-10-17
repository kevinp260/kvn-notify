"""Startup checks, run by `manage.py check`, runserver and migrate.

Each message links to its entry on the troubleshooting page.
"""

from __future__ import annotations

import importlib.util

from django.core.checks import Error, Tags, Warning, register

from kvn_notify.conf import VALID_DISPATCH, docs_link, notify_settings

ID = "kvn_notify.{}"


def _problem(code: str, msg: str, hint: str = "", *, strict: bool = False):
    level = Error if strict else (Error if code.startswith("E") else Warning)
    full_hint = f"{hint} See {docs_link(code.lower())}".strip()
    return level(msg, hint=full_hint, id=ID.format(code))


@register(Tags.compatibility)
def check_settings(app_configs=None, **kwargs):
    from kvn_notify.channels import channel_names
    from kvn_notify.types import all_types

    problems = []
    types = [t for t in all_types() if not t.key.startswith("kvn_notify.")]
    used = {name for t in types for name in (*t.channels, t.fallback) if name}

    if notify_settings.DISPATCH not in VALID_DISPATCH:
        problems.append(
            _problem(
                "E001",
                f"KVN_NOTIFY['DISPATCH'] is {notify_settings.DISPATCH!r}.",
                f"Use one of: {', '.join(VALID_DISPATCH)}.",
            )
        )
    elif notify_settings.DISPATCH == "celery" and importlib.util.find_spec("celery") is None:
        problems.append(
            _problem(
                "E002",
                "DISPATCH is 'celery' but Celery is not installed.",
                "pip install 'kvn-notify[celery]', or pick another dispatch mode.",
            )
        )

    auth = notify_settings.AUTH
    if auth == "drf" and importlib.util.find_spec("rest_framework") is None:
        problems.append(
            _problem(
                "E003",
                "AUTH is 'drf' but Django REST framework is not installed.",
                "pip install 'kvn-notify[drf]', or set AUTH to 'session'.",
            )
        )

    known = set(channel_names())
    for ntype in types:
        for name in (*ntype.channels, ntype.fallback):
            if name and name not in known:
                problems.append(
                    _problem(
                        "E004",
                        f"Notification type {ntype.key!r} uses unknown channel {name!r}.",
                        f"Known channels: {', '.join(sorted(known))}.",
                    )
                )

    if "push" in used or not types:
        missing = [
            k
            for k in ("VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_SUBJECT")
            if not getattr(notify_settings, k)
        ]
        if missing:
            problems.append(
                _problem(
                    "W001",
                    f"Web Push is not configured: {', '.join(missing)} missing in KVN_NOTIFY.",
                    "Run `python manage.py notify_vapid_keys` and add the output to your settings.",
                )
            )

    if "inbox" in used and not notify_settings.INBOX:
        problems.append(
            _problem(
                "W008",
                "A notification type uses the 'inbox' channel but KVN_NOTIFY['INBOX'] "
                "is False, so nothing is added to the list.",
                "Set 'INBOX': True.",
            )
        )

    if "email" in used and not notify_settings.SITE_URL:
        problems.append(
            _problem(
                "W009",
                "KVN_NOTIFY['SITE_URL'] is empty, so emails cannot include links.",
                "Set it to your public address, e.g. 'https://app.example.com'.",
            )
        )

    if "push" in used or not types:
        problems.extend(_icon_problems())
    return problems


def _icon_problems():
    from kvn_notify.icons import badge_problems, find_image_file, inspect_image, is_url

    strict = bool(notify_settings.STRICT_ICONS)
    problems = []
    badge, icon = notify_settings.BADGE, notify_settings.ICON

    if not badge:
        problems.append(
            _problem(
                "W002",
                "No push badge is set, so phones show the browser's default icon.",
                "Set KVN_NOTIFY['BADGE'] to a 96x96 white symbol on a transparent "
                "background. `python manage.py notify_make_badge` can make one from "
                "your logo.",
                strict=strict,
            )
        )
    elif not is_url(badge):
        path = find_image_file(badge)
        if path is None:
            problems.append(
                _problem(
                    "W006", f"The push badge {badge!r} was not found in your static files.", strict=strict
                )
            )
        elif importlib.util.find_spec("PIL") is not None:
            try:
                report = inspect_image(path)
            except Exception as exc:
                problems.append(
                    _problem("W006", f"The push badge {badge!r} could not be read: {exc}", strict=strict)
                )
            else:
                for code, message in badge_problems(report):
                    problems.append(
                        _problem(
                            code,
                            message,
                            "Run `python manage.py notify_make_badge <your-logo.png>`.",
                            strict=strict,
                        )
                    )

    if icon and not is_url(icon):
        path = find_image_file(icon)
        if path is None:
            problems.append(
                _problem("W006", f"The push icon {icon!r} was not found in your static files.", strict=strict)
            )
        elif importlib.util.find_spec("PIL") is not None:
            try:
                report = inspect_image(path)
            except Exception:
                report = None
            if report and min(report.width, report.height) < 192:
                problems.append(
                    _problem(
                        "W007",
                        f"The push icon is {report.width}x{report.height}; use at least 192x192.",
                        strict=strict,
                    )
                )
    return problems
