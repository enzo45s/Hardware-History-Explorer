# syntax=docker/dockerfile:1
FROM python:3.12-slim
WORKDIR /code
COPY requirements.lock .
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements.lock
COPY app ./app
COPY migrations ./migrations
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
