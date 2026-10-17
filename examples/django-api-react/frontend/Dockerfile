# Built from the repository root (see ../compose.yaml) so it uses this copy of kvn-notify-web.
FROM node:22-slim
WORKDIR /app
# package.json points at ../../../js, which from /app is /js.
COPY js /js
COPY examples/django-api-react/frontend/package.json examples/django-api-react/frontend/package-lock.json /app/
RUN npm install --no-audit --no-fund
COPY examples/django-api-react/frontend /app
