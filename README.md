# OpenClaw API Permission Manager / Interposer

This project provides a small policy enforcement gateway that sits between OpenClaw (or any internal app) and sensitive external APIs.

## What it does

- **Interposes** all outbound API calls through `/v1/proxy/{api_name}/{path}`.
- Uses **internal API keys** for local clients (OpenClaw, agents, scripts).
- Uses **permission rules** (`method + path glob`) per upstream API.
- Supports **read-only mode** that blocks non-read methods globally per upstream API.
- Stores and manages **upstream credentials** (e.g., Canvas bearer token).
- Includes a **web UI** to:
  - add/edit upstream APIs,
  - define permission rules,
  - create internal keys,
  - assign grants to each internal client,
  - inspect audit logs.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Open `http://localhost:8080`.

## Canvas default setup

On first boot, a default `canvas` upstream API is seeded with read-oriented rules and high-risk rules disabled by default.

1. Open UI.
2. Locate **canvas**.
3. Replace placeholder token using API update endpoint (or quick DB edit).
4. Create an internal client named `openclaw` and copy the generated key.
5. Grant only the `GET` permissions you want.

Example proxied request:

```bash
curl -H "X-Interposer-Key: <internal-key>" \
  "http://localhost:8080/v1/proxy/canvas/courses/123/assignments"
```

## Permission model

A request is allowed only if all checks pass:

1. Internal key is valid and active.
2. Upstream API exists and is enabled.
3. If upstream is in read-only mode, method must be `GET`/`HEAD`/`OPTIONS`.
4. A permission rule exists for `method + path` and is enabled.
5. Calling client is explicitly granted that permission rule.

Otherwise the request is denied and logged.

## Notes

- Current secret storage is plaintext in SQLite; place this app behind host-level protections and encrypted disk.
- For production hardening, add:
  - encrypted secrets (KMS/Vault),
  - RBAC + login for UI,
  - rate limits,
  - structured SIEM logging.
