"""Rendering each notification in its recipient's language.

KVN_NOTIFY["LANGUAGE_FOR_USER"] names a function that returns a user's language
code ("sq", "en", ...) or None. While a recipient's copy is rendered (title, body,
link, email), that language is active, so gettext, {% translate %}, lazy strings
and date formats come out in it. Without the setting, or when the function
returns None, the language active when notify() runs is used, as before.
"""

from __future__ import annotations

import contextlib
import logging

from django.utils import translation
from django.utils.module_loading import import_string

from kvn_notify.conf import notify_settings

logger = logging.getLogger("kvn_notify")


def language_for(user) -> str | None:
    setting = notify_settings.LANGUAGE_FOR_USER
    if not setting or user is None:
        return None
    find = import_string(setting) if isinstance(setting, str) else setting
    try:
        language = find(user)
    except Exception:  # a bad profile must not stop the notification
        logger.exception("kvn-notify: LANGUAGE_FOR_USER failed for user %s", getattr(user, "pk", None))
        return None
    return str(language) if language else None


def in_language_of(user):
    """Context manager: activate `user`'s language, or change nothing if unknown."""
    language = language_for(user)
    return translation.override(language) if language else contextlib.nullcontext()
