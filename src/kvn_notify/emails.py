"""Rendering notification emails.

Three levels of customisation, none required:
1. KVN_NOTIFY["EMAIL"] settings: brand name, logo, colour, footer.
2. Override the layout: templates/kvn_notify/email/base.html (and base.txt) in the project.
3. Per type: email_template="app/email/thing" -> thing.html, thing.txt, thing_subject.txt.
"""

from __future__ import annotations

import html

from django.template import Context, TemplateDoesNotExist
from django.template.loader import get_template, render_to_string

from kvn_notify.conf import notify_settings

BASE_HTML = "kvn_notify/email/base.html"
BASE_TEXT = "kvn_notify/email/base.txt"


def absolute_url(url: str) -> str:
    if not url or url.startswith(("http://", "https://", "mailto:")):
        return url
    site = (notify_settings.SITE_URL or "").rstrip("/")
    if not site:
        return ""  # a relative link is useless in an email
    return f"{site}/{url.lstrip('/')}"


def _render_text(name: str, context: dict) -> str:
    """Render a plain-text template without HTML escaping ("&" must stay "&")."""
    template = get_template(name)
    inner = getattr(template, "template", None)  # the Django engine's own Template
    if inner is not None:
        return inner.render(Context(context, autoescape=False))
    return html.unescape(template.render(context))  # other template engines


def _optional_text(name: str, context: dict) -> str | None:
    try:
        return _render_text(name, context)
    except TemplateDoesNotExist:
        return None


def render_email(ntype, notification, context: dict) -> tuple[str, str, str]:
    """Return (subject, text, html) for one notification."""
    email = notify_settings.EMAIL
    action_url = absolute_url(notification.url)
    full_context = {
        **context,
        "notification": notification,
        "title": notification.title,
        "body": notification.body,
        "action_url": action_url,
        "recipient": notification.user,
        "brand": email,
        "site_url": notify_settings.SITE_URL,
    }

    if ntype.email_subject:
        subject = ntype.render("email_subject", context)
    else:
        subject = notification.title

    text = None
    if ntype.email_template:
        base = ntype.email_template
        html_body = render_to_string(f"{base}.html", full_context)
        text = _optional_text(f"{base}.txt", full_context)
        custom_subject = _optional_text(f"{base}_subject.txt", full_context)
        if custom_subject:
            subject = custom_subject
    else:
        html_body = render_to_string(BASE_HTML, full_context)

    if text is None:
        # Built from the parts, not by stripping the HTML, which reads badly.
        text = _render_text(BASE_TEXT, full_context)

    subject = " ".join(subject.split())[:255]  # headers cannot contain newlines
    return subject, text.strip() + "\n", html_body
