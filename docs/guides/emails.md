# Emails and templates

**Every email is sent as HTML with a plain-text copy, using a default layout that needs no
template at all.** You can restyle or replace it at three levels; none of them is required.

With no customisation an email shows your brand name or logo, the notification's title and body,
and a button to its link.

!!! info "Links need `SITE_URL`"

    Notification links are usually relative (`/orders/12`). Emails need full addresses, so set
    `SITE_URL` to your public origin, e.g. `"https://app.example.com"`. Without it, emails are
    sent without the button, and `manage.py check` warns you (W009).

## Level 1: settings only

```python
KVN_NOTIFY = {
    # ...
    "EMAIL": {
        "FROM": "Shop <hello@shop.example>",   # default: DEFAULT_FROM_EMAIL
        "BRAND_NAME": "Shop",
        "LOGO_URL": "https://shop.example/static/logo-email.png",
        "PRIMARY_COLOR": "#2F9E8A",            # the button
        "FOOTER_TEXT": "You get this because you have an account at Shop.",
    },
}
```

## Level 2: replace the whole layout

The layout lives at `kvn_notify/email/base.html` and `kvn_notify/email/base.txt`. Create a file
with the same path in your project's templates folder and Django uses yours, the same way you
override the admin's templates:

```text
yourproject/templates/kvn_notify/email/base.html
```

Make sure the folder is in `TEMPLATES["DIRS"]`, or put it in an app listed **before**
`kvn_notify` in `INSTALLED_APPS`.

Start from a copy of the [default layout](https://github.com/kevinp260/kvn-notify/blob/main/src/kvn_notify/templates/kvn_notify/email/base.html).
It has these blocks: `header`, `content`, `action`, `action_label` and `footer`.

## Level 3: a template per type

```python
register(NotificationType(
    key="leave.approved",
    channels=["email"],
    title="Your leave request was approved",
    email_template="leaves/email/approved",
))
```

kvn-notify then looks for:

| File | Required | Used for |
| --- | --- | --- |
| `leaves/email/approved.html` | yes | The HTML email |
| `leaves/email/approved.txt` | no | The plain-text copy |
| `leaves/email/approved_subject.txt` | no | The subject line |

The HTML can extend the layout and fill only the middle, keeping your header and footer:

```django
{% extends "kvn_notify/email/base.html" %}

{% block content %}
  <p>Hi {{ recipient.first_name }},</p>
  <p>Your {{ leave.leave_type.name }} for {{ dates }} was approved.</p>
{% endblock %}

{% block action_label %}See your requests{% endblock %}
```

### What templates can use

| Variable | Contains |
| --- | --- |
| Everything you passed to `notify()` | e.g. `leave`, `dates` |
| `recipient` | The user, or `None` for an email address recipient |
| `title`, `body` | The rendered text |
| `action_url` | The full link, built from `url` and `SITE_URL` |
| `notification` | The saved notification |
| `brand` | The `EMAIL` settings: `brand.BRAND_NAME`, `brand.PRIMARY_COLOR`, ... |
| `site_url` | `SITE_URL` |

## Rules that keep emails working

- **Plain text is always included.** Without a `.txt` template it is built from the title, body
  and link, not by stripping the HTML.
- **Inline styles only.** Gmail and Outlook drop most `<style>` blocks. The default layout uses
  inline styles; if you write your own layout, do the same.
- **A broken template never breaks your request.** The email delivery fails with the template
  error, which you can see in the admin; push and inbox deliveries still go out.
- **Emails are rendered when `notify()` runs**, while your objects exist, and stored with the
  notification. A retry sends exactly the same email.
