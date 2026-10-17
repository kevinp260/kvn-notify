# Quick start

Pick the guide that matches how your project renders its pages. Both take about 15 minutes and
end with a test notification on your own device.

| Your project | Guide | Example project |
| --- | --- | --- |
| Pages are Django templates | [Django with templates](templates.md) | [`examples/django-templates`](https://github.com/kevinp260/kvn-notify/tree/main/examples/django-templates) |
| Django serves an API; React, Vue, Svelte or another frontend renders the pages | [Django API + any frontend](frontend.md) | [`examples/django-api-react`](https://github.com/kevinp260/kvn-notify/tree/main/examples/django-api-react) |

Not sure? If your frontend has its own `package.json` and build step, use the second guide.

!!! tip "Try an example first"

    Each example starts with one command, `docker compose up --build`, so you can see the whole
    flow working before you touch your own project.
