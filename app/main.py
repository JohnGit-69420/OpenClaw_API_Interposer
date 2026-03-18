from __future__ import annotations

from fnmatch import fnmatch
from typing import Any
from urllib.parse import urljoin

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, text
from sqlalchemy.orm import Session, joinedload

from .database import Base, SessionLocal, engine, get_db
from .models import AuditLog, ApiPermission, ClientPermission, ExternalAPI, InternalClient
from .security import generate_api_key, hash_key, mask_secret

app = FastAPI(title="OpenClaw API Permission Manager")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def setup_db() -> None:
    Base.metadata.create_all(bind=engine)
    migrate_schema()
    seed_defaults()


def migrate_schema() -> None:
    db = SessionLocal()
    try:
        columns = {
            row[1]
            for row in db.execute(text("PRAGMA table_info('internal_clients')")).fetchall()
        }
        if "api_key_value" not in columns:
            db.execute(text("ALTER TABLE internal_clients ADD COLUMN api_key_value TEXT"))
            db.commit()
    finally:
        db.close()


def seed_defaults() -> None:
    db = SessionLocal()
    try:
        canvas = db.query(ExternalAPI).filter_by(name="canvas").first()
        if not canvas:
            canvas = ExternalAPI(
                name="canvas",
                base_url="https://canvas.instructure.com/api/v1/",
                auth_type="bearer",
                auth_token="REPLACE_WITH_TOKEN",
                readonly_mode=True,
                enabled=True,
            )
            db.add(canvas)
            db.flush()

            defaults = [
                ("List courses", "GET", "courses*", "low"),
                ("List assignments", "GET", "courses/*/assignments*", "low"),
                ("Get assignment", "GET", "courses/*/assignments/*", "low"),
                ("List todos", "GET", "users/self/todo*", "low"),
                ("Messages endpoint", "POST", "conversations*", "high"),
                ("Submit assignment", "POST", "courses/*/assignments/*/submissions*", "high"),
            ]
            for name, method, path, risk in defaults:
                db.add(
                    ApiPermission(
                        api_id=canvas.id,
                        name=name,
                        method=method,
                        path_pattern=path,
                        risk=risk,
                        enabled=(risk == "low"),
                    )
                )
            db.commit()
    finally:
        db.close()


def log_decision(
    db: Session,
    *,
    client_name: str,
    api_name: str,
    method: str,
    path: str,
    decision: str,
    reason: str,
    upstream_status: str = "n/a",
) -> None:
    db.add(
        AuditLog(
            client_name=client_name,
            api_name=api_name,
            method=method,
            path=path,
            decision=decision,
            reason=reason,
            upstream_status=upstream_status,
        )
    )
    db.commit()


def get_client_from_key(db: Session, api_key: str | None) -> InternalClient:
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-Interposer-Key header")

    client = (
        db.query(InternalClient)
        .filter_by(api_key_hash=hash_key(api_key), active=True)
        .options(joinedload(InternalClient.permissions).joinedload(ClientPermission.permission))
        .first()
    )
    if not client:
        raise HTTPException(status_code=401, detail="Invalid or inactive key")
    return client


def has_client_permission(client: InternalClient, permission: ApiPermission) -> bool:
    for grant in client.permissions:
        if grant.permission_id == permission.id:
            return grant.allowed
    return False


@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    apis = db.query(ExternalAPI).options(joinedload(ExternalAPI.permissions)).all()
    clients = db.query(InternalClient).options(joinedload(InternalClient.permissions)).all()
    logs = db.query(AuditLog).order_by(desc(AuditLog.timestamp)).limit(30).all()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "apis": apis,
            "clients": clients,
            "logs": logs,
            "mask_secret": mask_secret,
        },
    )


@app.get("/api/state")
def state(db: Session = Depends(get_db)) -> dict[str, Any]:
    apis = db.query(ExternalAPI).options(joinedload(ExternalAPI.permissions)).all()
    clients = db.query(InternalClient).options(joinedload(InternalClient.permissions)).all()
    return {
        "apis": [
            {
                "id": api.id,
                "name": api.name,
                "base_url": api.base_url,
                "enabled": api.enabled,
                "readonly_mode": api.readonly_mode,
                "auth_type": api.auth_type,
                "token_preview": mask_secret(api.auth_token),
                "permissions": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "method": p.method,
                        "path_pattern": p.path_pattern,
                        "risk": p.risk,
                        "enabled": p.enabled,
                    }
                    for p in api.permissions
                ],
            }
            for api in apis
        ],
        "clients": [
            {
                "id": c.id,
                "name": c.name,
                "active": c.active,
                "api_key_value": c.api_key_value,
                "permission_ids": [cp.permission_id for cp in c.permissions if cp.allowed],
            }
            for c in clients
        ],
    }


@app.post("/api/apis")
async def create_api(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    payload = await request.json()
    api = ExternalAPI(
        name=payload["name"].strip(),
        base_url=payload["base_url"].rstrip("/") + "/",
        auth_type=payload.get("auth_type", "bearer"),
        auth_token=payload["auth_token"].strip(),
        enabled=bool(payload.get("enabled", True)),
        readonly_mode=bool(payload.get("readonly_mode", True)),
    )
    db.add(api)
    db.commit()
    return {"ok": True}


@app.delete("/api/apis/{api_id}")
def delete_api(api_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    api = db.query(ExternalAPI).filter_by(id=api_id).first()
    if not api:
        raise HTTPException(status_code=404, detail="API not found")
    db.delete(api)
    db.commit()
    return {"ok": True}


@app.post("/api/permissions")
async def create_permission(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    payload = await request.json()
    permission = ApiPermission(
        api_id=int(payload["api_id"]),
        name=payload["name"].strip(),
        method=payload["method"].upper().strip(),
        path_pattern=payload["path_pattern"].lstrip("/"),
        risk=payload.get("risk", "low"),
        enabled=bool(payload.get("enabled", True)),
    )
    db.add(permission)
    db.commit()
    return {"ok": True}


@app.delete("/api/permissions/{permission_id}")
def delete_permission(permission_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    permission = db.query(ApiPermission).filter_by(id=permission_id).first()
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    db.delete(permission)
    db.commit()
    return {"ok": True}


@app.post("/api/clients")
async def create_client(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    payload = await request.json()
    raw_key = generate_api_key()
    auto_grant_readonly = bool(payload.get("auto_grant_readonly", True))
    client = InternalClient(
        name=payload["name"].strip(),
        api_key_hash=hash_key(raw_key),
        api_key_value=raw_key,
        active=True,
    )
    db.add(client)
    db.flush()

    if auto_grant_readonly:
        readonly_perms = (
            db.query(ApiPermission)
            .join(ExternalAPI, ExternalAPI.id == ApiPermission.api_id)
            .filter(
                ApiPermission.enabled.is_(True),
                ApiPermission.method.in_({"GET", "HEAD", "OPTIONS"}),
                ExternalAPI.enabled.is_(True),
            )
            .all()
        )
        for perm in readonly_perms:
            db.add(
                ClientPermission(
                    client_id=client.id,
                    permission_id=perm.id,
                    allowed=True,
                )
            )
    db.commit()
    return {"ok": True, "api_key": raw_key, "auto_granted_readonly": auto_grant_readonly}


@app.delete("/api/clients/{client_id}")
def delete_client(client_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = db.query(InternalClient).filter_by(id=client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(client)
    db.commit()
    return {"ok": True}


@app.post("/api/clients/{client_id}/rotate-key")
def rotate_client_key(client_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = db.query(InternalClient).filter_by(id=client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    raw_key = generate_api_key()
    client.api_key_hash = hash_key(raw_key)
    client.api_key_value = raw_key
    db.commit()
    return {"ok": True, "api_key": raw_key}


@app.patch("/api/clients/{client_id}")
async def update_client(client_id: int, request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    client = db.query(InternalClient).filter_by(id=client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if "active" in payload:
        client.active = bool(payload["active"])
    if "name" in payload and payload["name"].strip():
        client.name = payload["name"].strip()
    db.commit()
    return {"ok": True}


@app.post("/api/clients/{client_id}/permissions")
async def set_client_permissions(
    client_id: int, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    payload = await request.json()
    allowed_ids = {int(p) for p in payload.get("permission_ids", [])}

    db.query(ClientPermission).filter_by(client_id=client_id).delete()
    for permission_id in allowed_ids:
        db.add(
            ClientPermission(client_id=client_id, permission_id=permission_id, allowed=True)
        )
    db.commit()
    return {"ok": True}


@app.post("/api/clients/{client_id}/grant-readonly")
def grant_readonly_defaults(client_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = db.query(InternalClient).filter_by(id=client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    readonly_perms = (
        db.query(ApiPermission)
        .join(ExternalAPI, ExternalAPI.id == ApiPermission.api_id)
        .filter(
            ApiPermission.enabled.is_(True),
            ApiPermission.method.in_({"GET", "HEAD", "OPTIONS"}),
            ExternalAPI.enabled.is_(True),
        )
        .all()
    )
    readonly_ids = {perm.id for perm in readonly_perms}
    existing = {
        cp.permission_id
        for cp in db.query(ClientPermission).filter_by(client_id=client_id, allowed=True).all()
    }

    for permission_id in sorted(readonly_ids - existing):
        db.add(
            ClientPermission(
                client_id=client_id,
                permission_id=permission_id,
                allowed=True,
            )
        )
    db.commit()
    return {"ok": True, "granted_count": len(readonly_ids - existing)}


@app.patch("/api/apis/{api_id}")
async def update_api(api_id: int, request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    api = db.query(ExternalAPI).filter_by(id=api_id).first()
    if not api:
        raise HTTPException(status_code=404, detail="API not found")
    api.enabled = bool(payload.get("enabled", api.enabled))
    api.readonly_mode = bool(payload.get("readonly_mode", api.readonly_mode))
    if "auth_token" in payload and payload["auth_token"].strip():
        api.auth_token = payload["auth_token"].strip()
    db.commit()
    return {"ok": True}


@app.patch("/api/permissions/{permission_id}")
async def update_permission(
    permission_id: int, request: Request, db: Session = Depends(get_db)
):
    payload = await request.json()
    permission = db.query(ApiPermission).filter_by(id=permission_id).first()
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    permission.enabled = bool(payload.get("enabled", permission.enabled))
    permission.risk = payload.get("risk", permission.risk)
    db.commit()
    return {"ok": True}


@app.api_route(
    "/v1/proxy/{api_name}/{target_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def proxy_request(
    api_name: str,
    target_path: str,
    request: Request,
    x_interposer_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    method = request.method.upper()
    normalized_path = target_path.lstrip("/")

    client = get_client_from_key(db, x_interposer_key)
    api = (
        db.query(ExternalAPI)
        .filter_by(name=api_name, enabled=True)
        .options(joinedload(ExternalAPI.permissions))
        .first()
    )
    if not api:
        log_decision(
            db,
            client_name=client.name,
            api_name=api_name,
            method=method,
            path=normalized_path,
            decision="deny",
            reason="Unknown or disabled upstream API",
        )
        raise HTTPException(status_code=404, detail="Unknown API")

    if api.readonly_mode and method not in {"GET", "HEAD", "OPTIONS"}:
        log_decision(
            db,
            client_name=client.name,
            api_name=api_name,
            method=method,
            path=normalized_path,
            decision="deny",
            reason="API currently locked to read-only methods",
        )
        raise HTTPException(status_code=403, detail="API read-only mode blocks this method")

    matching = [
        p
        for p in api.permissions
        if p.enabled and p.method.upper() == method and fnmatch(normalized_path, p.path_pattern)
    ]
    if not matching:
        log_decision(
            db,
            client_name=client.name,
            api_name=api.name,
            method=method,
            path=normalized_path,
            decision="deny",
            reason="No permission rule matched request",
        )
        raise HTTPException(status_code=403, detail="No matching permission rule")

    chosen = matching[0]
    if not has_client_permission(client, chosen):
        log_decision(
            db,
            client_name=client.name,
            api_name=api.name,
            method=method,
            path=normalized_path,
            decision="deny",
            reason="Client lacks grant for matched rule",
        )
        raise HTTPException(status_code=403, detail="Client is not granted this rule")

    upstream_url = urljoin(api.base_url, normalized_path)
    body = await request.body()
    headers = {"Authorization": f"Bearer {api.auth_token}"}

    async with httpx.AsyncClient(timeout=20.0) as client_http:
        upstream_response = await client_http.request(
            method=method,
            url=upstream_url,
            content=body if body else None,
            headers=headers,
            params=dict(request.query_params),
        )

    log_decision(
        db,
        client_name=client.name,
        api_name=api.name,
        method=method,
        path=normalized_path,
        decision="allow",
        reason=f"Rule {chosen.name}",
        upstream_status=str(upstream_response.status_code),
    )

    filtered_headers = {
        key: value
        for key, value in upstream_response.headers.items()
        if key.lower() in {"content-type", "content-length"}
    }
    try:
        payload: Any = upstream_response.json() if upstream_response.text else {}
    except ValueError:
        payload = {"raw": upstream_response.text}

    return JSONResponse(
        status_code=upstream_response.status_code,
        content=payload,
        headers=filtered_headers,
    )
