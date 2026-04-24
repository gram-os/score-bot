import hashlib
import hmac
import json
import os
import subprocess
import threading

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

app = FastAPI()

WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
REPO_PATH = os.environ["REPO_PATH"]
MAX_BODY_BYTES = 25 * 1024

_deploy_lock = threading.Lock()


def verify_signature(payload: bytes, signature: str) -> bool:
    expected = "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def run_deploy() -> None:
    if not _deploy_lock.acquire(blocking=False):
        return
    try:
        subprocess.run(["git", "pull", "origin", "main"], cwd=REPO_PATH, check=True)
        subprocess.run(["make", "restart"], cwd=REPO_PATH, check=True)
    finally:
        _deploy_lock.release()


@app.post("/deploy")
async def deploy(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    if int(request.headers.get("content-length", 0)) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")

    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    data = json.loads(payload)
    ref = data.get("ref", "")

    if ref != "refs/heads/main":
        return JSONResponse({"status": "skipped", "ref": ref})

    background_tasks.add_task(run_deploy)
    return JSONResponse({"status": "accepted"})
