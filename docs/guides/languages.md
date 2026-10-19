# Languages

**Each recipient can get their notifications in their own language.** Without this, text is
rendered in whatever language is active when `notify()` runs, usually the language of the person
whose action caused it: a coach writing in English would send English notifications to Albanian
players.

## Tell kvn-notify each user's language

Point `LANGUAGE_FOR_USER` at a function that returns a language code, or `None` to leave the
current language:

```python
# myapp/notify_language.py
def user_language(user):
    return user.profile.language  # "sq", "en", ...


KVN_NOTIFY = {"LANGUAGE_FOR_USER": "myapp.notify_language.user_language", ...}
```

While a recipient's copy is rendered (push title, body and link, and the email), their language is
active. Anything translated with Django's usual tools comes out in it:

- `gettext_lazy` strings in a type's text, or `gettext` inside a callable;
- `{% translate %}` and `{% blocktranslate %}` in email templates;
- dates and numbers formatted with Django's localization.

```python
from django.utils.translation import gettext_lazy as _

register(NotificationType(
    key="event.cancelled",
    title=_("Cancelled: {event_name}"),
    body=_("Was {when}"),
))
```

The strings are translated like the rest of your app (`makemessages`, `compilemessages`).

## Good to know

- If the function fails (a missing profile, say), the notification is still sent, in the current
  language, and the error is logged.
- Recipients given as plain email addresses have no user, so they get the current language.
- Fallback messages to `fallback_recipients` are rendered once, in the current language.
- Values you pass in the context are used as they are. Format dates and amounts inside the type
  (a callable, or the email template) rather than before calling `notify()`, so they follow the
  recipient's language.
