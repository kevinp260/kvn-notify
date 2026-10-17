# Built from the repository root (see ../compose.yaml) so it installs this copy of kvn-notify.
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY pyproject.toml README.md LICENSE /kvn-notify/
COPY src /kvn-notify/src
RUN pip install "/kvn-notify[drf]" "djangorestframework-simplejwt>=5.3"
COPY examples/django-api-react/backend /app
