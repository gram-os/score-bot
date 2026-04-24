import hashlib
import hmac
import json
import logging
import os
import subprocess
import threading

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)

app = FastAPI()

WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
REPO_PATH = os.environ["REPO_PATH"]
MAX_BODY_BYTES = 25 * 1024

_deploy_lock = threading.Lock()


def verify_signature(payload: bytes, signature: str) -> bool:
    expected = "sha256=" + hmac.HMAC(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def run_deploy() -> None:
    if not _deploy_lock.acquire(blocking=False):
        log.info("Deploy already in progress, skipping")
        return
    try:
        subprocess.run(["git", "pull", "origin", "main"], cwd=REPO_PATH, check=True)
        subprocess.run(["make", "restart"], cwd=REPO_PATH, check=True)
        log.info("Deploy completed successfully")
    except subprocess.CalledProcessError as e:
        log.error("Deploy failed: %s", e)
    finally:
        _deploy_lock.release()


@app.post("/deploy")
async def deploy(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    payload = await request.body()
    if len(payload) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")

    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    ref = data.get("ref", "")

    if ref != "refs/heads/main":
        return JSONResponse({"status": "skipped", "ref": ref})

    background_tasks.add_task(run_deploy)
    return JSONResponse({"status": "accepted"})
