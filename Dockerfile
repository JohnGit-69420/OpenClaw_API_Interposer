FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

COPY app /app/app
COPY static /app/static
COPY templates /app/templates
COPY README.md /app/README.md

RUN useradd --create-home --shell /bin/bash appuser && mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

ENV WEBUI_SESSION_SECRET="change-me" \
    PORT=8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
