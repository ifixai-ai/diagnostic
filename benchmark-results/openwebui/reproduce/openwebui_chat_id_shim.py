"""Tiny adapter: accept OpenAI-compatible chat completions and forward to
Open WebUI's /api/chat/completions, injecting the chat_id field that OWUI
requires but standard OpenAI clients don't send.

Listens on :8090. Forwards to :8080 (Open WebUI).

Usage:
    OWUI_TOKEN=<jwt> .venv-openwebui/bin/python /tmp/owui_shim.py
"""
from __future__ import annotations

import os
import sys
import uuid
import asyncio
import logging
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("owui-shim")

OWUI_BASE = os.environ.get("OWUI_BASE", "http://127.0.0.1:8080")
OWUI_TOKEN = os.environ.get("OWUI_TOKEN", "")
PORT = int(os.environ.get("SHIM_PORT", "8090"))

app = FastAPI(title="OWUI OpenAI-compat shim")


@app.get("/")
async def root() -> dict[str, Any]:
    return {"ok": True, "shim": "openwebui-openai-compat", "forwards_to": OWUI_BASE}


@app.get("/v1/models")
async def list_models(authorization: str | None = Header(default=None)) -> JSONResponse:
    token = authorization or f"Bearer {OWUI_TOKEN}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{OWUI_BASE}/api/models",
            headers={"Authorization": token if token.startswith("Bearer ") else f"Bearer {token}"},
        )
    return JSONResponse(content=r.json(), status_code=r.status_code)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> JSONResponse:
    payload = await request.json()
    # Inject chat_id the way Open WebUI's /api/chat/completions expects
    chat_id = payload.get("chat_id") or f"local:ifixai-{uuid.uuid4().hex[:12]}"
    payload["chat_id"] = chat_id
    payload["id"] = chat_id

    auth = request.headers.get("authorization") or (f"Bearer {OWUI_TOKEN}" if OWUI_TOKEN else "")
    if not auth.startswith("Bearer "):
        auth = f"Bearer {auth}"

    headers = {
        "Authorization": auth,
        "Content-Type": "application/json",
    }

    timeout = httpx.Timeout(connect=30.0, read=240.0, write=30.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            r = await client.post(f"{OWUI_BASE}/api/chat/completions", json=payload, headers=headers)
        except httpx.RequestError as exc:
            log.error("upstream request error: %s", exc)
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        body = r.json()
    except Exception:
        body = {"error": {"message": r.text[:4000]}}
    if r.status_code >= 400:
        log.warning("upstream %d: %s", r.status_code, str(body)[:500])
    return JSONResponse(content=body, status_code=r.status_code)


if __name__ == "__main__":
    import uvicorn
    if not OWUI_TOKEN:
        print("WARNING: OWUI_TOKEN not set — requests must carry their own Authorization header", file=sys.stderr)
    print(f"OWUI shim listening on http://127.0.0.1:{PORT} -> {OWUI_BASE}", file=sys.stderr)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
