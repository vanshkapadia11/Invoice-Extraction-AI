from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Header,
    HTTPException,
    Request,
    BackgroundTasks,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from transformers import DonutProcessor, VisionEncoderDecoderModel
from PIL import Image
import torch
import io
import sqlite3
import secrets
import time
import re
import uuid
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from enum import Enum
from pathlib import Path

# ─── File Logger Setup ───────────────────────────────────────
log_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

file_handler = RotatingFileHandler(
    "invoice_api.log",
    maxBytes=5 * 1024 * 1024,  # 5MB per file
    backupCount=5,  # keeps last 5 rotated files
    encoding="utf-8",
)
file_handler.setFormatter(log_formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

logger = logging.getLogger("invoice_api")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)


# ─── Tier Definitions ────────────────────────────────────────
class Tier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


TIER_LIMITS = {
    Tier.FREE: {"rpm": 5, "rpd": 20, "max_file_mb": 5},
    Tier.PRO: {"rpm": 30, "rpd": 500, "max_file_mb": 20},
    Tier.ENTERPRISE: {"rpm": 200, "rpd": 10000, "max_file_mb": 50},
}

# ─── Job Queue ───────────────────────────────────────────────
jobs: Dict[str, Dict[str, Any]] = {}

# ─── Database ────────────────────────────────────────────────
DB_PATH = "invoice.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            key         TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            is_active   INTEGER DEFAULT 1,
            tier        TEXT DEFAULT 'free',
            rpm_limit   INTEGER DEFAULT 5,
            rpd_limit   INTEGER DEFAULT 20,
            expires_at  TEXT DEFAULT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS usage_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key     TEXT NOT NULL,
            endpoint    TEXT NOT NULL,
            status      INTEGER NOT NULL,
            latency_ms  REAL DEFAULT 0,
            ip_address  TEXT DEFAULT '',
            file_name   TEXT DEFAULT '',
            timestamp   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS webhooks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key     TEXT NOT NULL,
            url         TEXT NOT NULL,
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()

    existing = conn.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0]
    if existing == 0:
        admin_key = "admin-" + secrets.token_hex(16)
        conn.execute(
            "INSERT INTO api_keys (key, name, tier, rpm_limit, rpd_limit) VALUES (?, ?, ?, ?, ?)",
            (admin_key, "Admin", "enterprise", 200, 10000),
        )
        conn.commit()
        logger.info("=" * 60)
        logger.info(f"  ADMIN API KEY: {admin_key}")
        logger.info("=" * 60)
    conn.close()


init_db()

# ─── Rate Limiting ───────────────────────────────────────────
request_timestamps: dict = {}


def check_rate_limit(api_key: str, rpm: int, rpd: int):
    now = time.time()
    today = date.today().isoformat()
    key_data = request_timestamps.setdefault(api_key, {"minute": [], "day": {}})

    key_data["minute"] = [t for t in key_data["minute"] if now - t < 60]
    if len(key_data["minute"]) >= rpm:
        logger.warning(f"Rate limit hit | key={api_key[:12]}... | rpm={rpm}")
        raise HTTPException(
            status_code=429, detail=f"Rate limit: {rpm} req/min. Slow down."
        )
    key_data["minute"].append(now)

    day_count = key_data["day"].get(today, 0)
    if day_count >= rpd:
        logger.warning(f"Daily limit hit | key={api_key[:12]}... | rpd={rpd}")
        raise HTTPException(
            status_code=429, detail=f"Daily limit: {rpd} req/day reached."
        )
    key_data["day"][today] = day_count + 1


# ─── Auth ────────────────────────────────────────────────────
def verify_key(x_api_key: Optional[str] = None):
    if not x_api_key:
        logger.warning("Request with missing X-API-Key header")
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM api_keys WHERE key = ? AND is_active = 1", (x_api_key,)
    ).fetchone()
    conn.close()

    if not row:
        logger.warning(f"Invalid/inactive API key attempt: {x_api_key[:12]}...")
        raise HTTPException(status_code=403, detail="Invalid or inactive API key")

    row = dict(row)  # convert to plain dict

    if row.get("expires_at"):
        expires = datetime.fromisoformat(row["expires_at"])
        if datetime.now() > expires:
            logger.warning(f"Expired API key used: {x_api_key[:12]}...")
            raise HTTPException(status_code=403, detail="API key expired")

    check_rate_limit(x_api_key, row["rpm_limit"], row["rpd_limit"])
    return row


def require_admin(x_api_key: Optional[str] = None):
    key_info = verify_key(x_api_key)
    tier = key_info.get("tier", "")
    name = key_info.get("name", "")
    if tier != "enterprise" and name != "Admin":
        logger.warning(f"Unauthorized admin access attempt | key={x_api_key[:12]}...")
        raise HTTPException(status_code=403, detail="Admin access required")
    return key_info


# ─── DB + File Log ───────────────────────────────────────────
def log_request(
    api_key: str,
    endpoint: str,
    status: int,
    latency_ms: float = 0,
    ip: str = "",
    file_name: str = "",
):
    # ── Original DB log (kept as-is) ──
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO usage_logs (api_key, endpoint, status, latency_ms, ip_address, file_name) VALUES (?, ?, ?, ?, ?, ?)",
            (api_key, endpoint, status, latency_ms, ip, file_name),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"DB log insert failed: {e}")

    # ── Additional file log ──
    log_line = (
        f"endpoint={endpoint} | status={status} | "
        f"latency={round(latency_ms, 2)}ms | key={api_key[:12]}... | "
        f"ip={ip} | file={file_name}"
    )
    if status < 400:
        logger.info(log_line)
    elif status < 500:
        logger.warning(log_line)
    else:
        logger.error(log_line)


# ─── Model ───────────────────────────────────────────────────
logger.info("Loading model...")
MODEL_PATH = Path(r"C:\Work\My College Work\Projects\invoice-project\donut-finetuned")

processor = DonutProcessor.from_pretrained(MODEL_PATH, local_files_only=True)
model = VisionEncoderDecoderModel.from_pretrained(MODEL_PATH, local_files_only=True)

new_tokens = [
    "<s_invoice>",
    "</s_invoice>",
    "<s_invoice_no>",
    "</s_invoice_no>",
    "<s_invoice_date>",
    "</s_invoice_date>",
    "<s_seller>",
    "</s_seller>",
    "<s_client>",
    "</s_client>",
    "<s_total>",
    "</s_total>",
    "<s_tax>",
    "</s_tax>",
]
processor.tokenizer.add_tokens(new_tokens)
model.decoder.resize_token_embeddings(len(processor.tokenizer))
model.config.decoder_start_token_id = processor.tokenizer.convert_tokens_to_ids(
    "<s_invoice>"
)
model.eval()

device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)
logger.info(f"Model ready on {device} ✅")


# ─── Core Extraction ─────────────────────────────────────────
def extract_from_image(image: Image.Image, retries: int = 3) -> dict:
    processor.image_processor.size = {"height": 720, "width": 480}
    pixel_values = processor(image, return_tensors="pt").pixel_values.to(device)

    task_prompt = "<s_invoice>"
    decoder_input_ids = processor.tokenizer(
        task_prompt, add_special_tokens=False, return_tensors="pt"
    ).input_ids.to(device)

    for attempt in range(retries):
        try:
            with torch.no_grad():
                outputs = model.generate(
                    pixel_values,
                    decoder_input_ids=decoder_input_ids,
                    max_length=512,
                    pad_token_id=processor.tokenizer.pad_token_id,
                    eos_token_id=processor.tokenizer.eos_token_id,
                    use_cache=True,
                    bad_words_ids=[[processor.tokenizer.unk_token_id]],
                    return_dict_in_generate=True,
                )

            sequence = processor.batch_decode(outputs.sequences)[0]
            sequence = sequence.replace(processor.tokenizer.eos_token, "")
            sequence = sequence.replace(processor.tokenizer.pad_token, "")
            sequence = sequence.replace("<s>", "")
            start_idx = sequence.find("<s_invoice>")
            if start_idx != -1:
                sequence = sequence[start_idx:]

            result = processor.token2json(sequence)
            return result
        except Exception as e:
            logger.warning(f"Extraction attempt {attempt + 1}/{retries} failed: {e}")
            if attempt == retries - 1:
                logger.error(f"All {retries} extraction attempts failed")
                raise e
            time.sleep(0.5)


def add_confidence(result: dict) -> dict:
    """Add confidence scores per field based on content heuristics."""
    fields = result.get("invoice", result)
    scored = {}
    for k, v in fields.items():
        if not v or v == "":
            confidence = 0.0
        elif k == "invoice_no" and v.replace("-", "").isdigit():
            confidence = 0.97
        elif k == "invoice_date" and re.search(
            r"\d{2}[/-]\d{2}[/-]\d{4}|\d{4}[/-]\d{2}[/-]\d{2}", str(v)
        ):
            confidence = 0.95
        elif k in ("total", "tax") and re.search(r"[\d,\.]+", str(v)):
            confidence = 0.90
        elif k in ("seller", "client") and len(str(v)) > 5:
            confidence = 0.85
        else:
            confidence = 0.75
        scored[k] = {"value": v, "confidence": confidence}
    return scored


def load_image_from_bytes(content: bytes, filename: str) -> Image.Image:
    """Handle both image and PDF inputs."""
    if filename.lower().endswith(".pdf"):
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(stream=content, filetype="pdf")
            page = doc[0]
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            return Image.open(io.BytesIO(img_bytes)).convert("RGB")
        except ImportError:
            raise HTTPException(
                status_code=400, detail="PDF support requires: pip install pymupdf"
            )
    else:
        return Image.open(io.BytesIO(content)).convert("RGB")


# ─── Webhook ─────────────────────────────────────────────────
async def fire_webhook(api_key: str, job_id: str, result: dict):
    import httpx

    conn = get_db()
    rows = conn.execute(
        "SELECT url FROM webhooks WHERE api_key = ? AND is_active = 1", (api_key,)
    ).fetchall()
    conn.close()

    payload = {
        "job_id": job_id,
        "status": "done",
        "result": result,
        "timestamp": datetime.now().isoformat(),
    }
    async with httpx.AsyncClient() as client:
        for row in rows:
            try:
                await client.post(row["url"], json=payload, timeout=10)
                logger.info(f"Webhook fired | job={job_id} | url={row['url']}")
            except Exception as e:
                logger.warning(
                    f"Webhook delivery failed | job={job_id} | url={row['url']} | error={e}"
                )


# ─── App ─────────────────────────────────────────────────────
app = FastAPI(title="Invoice Parser API", version="2.0.0", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health ──────────────────────────────────────────────────
@app.get("/health")
def health():
    logger.info("Health check requested")
    return {
        "status": "ok",
        "model": "loaded",
        "device": device,
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "jobs_in_queue": len([j for j in jobs.values() if j["status"] == "processing"]),
    }


# ─── Sync Parse ──────────────────────────────────────────────
@app.post("/parse-invoice")
async def parse_invoice(
    request: Request,
    file: UploadFile = File(...),
    x_api_key: Optional[str] = Header(None),
):
    start = time.time()
    key_info = verify_key(x_api_key)
    ip = request.client.host

    tier = key_info.get("tier", "free")
    max_mb = TIER_LIMITS.get(tier, TIER_LIMITS[Tier.FREE])["max_file_mb"]

    contents = await file.read()

    if len(contents) > max_mb * 1024 * 1024:
        logger.warning(
            f"File too large | file={file.filename} | size={len(contents)} | max={max_mb}MB | ip={ip}"
        )
        raise HTTPException(
            status_code=413, detail=f"File too large. Max {max_mb}MB for {tier} tier."
        )

    logger.info(f"Parsing invoice | file={file.filename} | tier={tier} | ip={ip}")

    try:
        image = load_image_from_bytes(contents, file.filename or "")
        raw_result = extract_from_image(image)
        scored = add_confidence(raw_result)
        latency = (time.time() - start) * 1000
        log_request(
            key_info["key"], "/parse-invoice", 200, latency, ip, file.filename or ""
        )

        return {
            "success": True,
            "file": file.filename,
            "latency_ms": round(latency, 2),
            "tier": tier,
            "fields": scored,
        }

    except HTTPException:
        raise
    except Exception as e:
        latency = (time.time() - start) * 1000
        logger.error(f"Parse failed | file={file.filename} | error={e} | ip={ip}")
        log_request(
            key_info["key"], "/parse-invoice", 500, latency, ip, file.filename or ""
        )
        raise HTTPException(status_code=500, detail=str(e))


# ─── Async Job Submit ─────────────────────────────────────────
@app.post("/jobs/submit")
async def submit_job(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    x_api_key: Optional[str] = Header(None),
):
    key_info = verify_key(x_api_key)
    ip = request.client.host

    contents = await file.read()
    job_id = str(uuid.uuid4())

    jobs[job_id] = {
        "status": "queued",
        "file": file.filename,
        "submitted_at": datetime.now().isoformat(),
        "result": None,
        "error": None,
    }

    logger.info(f"Job queued | job_id={job_id} | file={file.filename} | ip={ip}")

    async def process_job():
        jobs[job_id]["status"] = "processing"
        logger.info(f"Job started | job_id={job_id}")
        start = time.time()
        try:
            image = load_image_from_bytes(contents, file.filename or "")
            raw_result = extract_from_image(image)
            scored = add_confidence(raw_result)
            latency = (time.time() - start) * 1000
            jobs[job_id].update(
                {
                    "status": "done",
                    "result": scored,
                    "latency_ms": round(latency, 2),
                    "completed_at": datetime.now().isoformat(),
                }
            )
            log_request(
                key_info["key"], "/jobs/submit", 200, latency, ip, file.filename or ""
            )
            logger.info(f"Job done | job_id={job_id} | latency={round(latency, 2)}ms")
            await fire_webhook(key_info["key"], job_id, scored)
        except Exception as e:
            jobs[job_id].update({"status": "failed", "error": str(e)})
            logger.error(f"Job failed | job_id={job_id} | error={e}")
            log_request(
                key_info["key"], "/jobs/submit", 500, 0, ip, file.filename or ""
            )

    background_tasks.add_task(process_job)

    return {"job_id": job_id, "status": "queued", "poll_url": f"/jobs/{job_id}"}


# ─── Job Status ───────────────────────────────────────────────
@app.get("/jobs/{job_id}")
def get_job(job_id: str, x_api_key: Optional[str] = Header(None)):
    verify_key(x_api_key)
    job = jobs.get(job_id)
    if not job:
        logger.warning(f"Job not found | job_id={job_id}")
        raise HTTPException(status_code=404, detail="Job not found")
    logger.info(f"Job status polled | job_id={job_id} | status={job.get('status')}")
    return job


# ─── Batch Submit ─────────────────────────────────────────────
@app.post("/batch/submit")
async def batch_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    x_api_key: Optional[str] = Header(None),
):
    key_info = verify_key(x_api_key)
    ip = request.client.host

    if len(files) > 20:
        logger.warning(f"Batch too large | count={len(files)} | ip={ip}")
        raise HTTPException(status_code=400, detail="Max 20 files per batch")

    batch_id = str(uuid.uuid4())
    job_ids = []

    logger.info(f"Batch submitted | batch_id={batch_id} | files={len(files)} | ip={ip}")

    for file in files:
        contents = await file.read()
        job_id = str(uuid.uuid4())
        job_ids.append(job_id)
        jobs[job_id] = {
            "status": "queued",
            "file": file.filename,
            "batch_id": batch_id,
            "submitted_at": datetime.now().isoformat(),
            "result": None,
            "error": None,
        }

        async def process(c=contents, fn=file.filename, jid=job_id):
            jobs[jid]["status"] = "processing"
            logger.info(
                f"Batch job started | job_id={jid} | file={fn} | batch_id={batch_id}"
            )
            start = time.time()
            try:
                image = load_image_from_bytes(c, fn or "")
                raw_result = extract_from_image(image)
                scored = add_confidence(raw_result)
                latency = (time.time() - start) * 1000
                jobs[jid].update(
                    {
                        "status": "done",
                        "result": scored,
                        "latency_ms": round(latency, 2),
                        "completed_at": datetime.now().isoformat(),
                    }
                )
                log_request(
                    key_info["key"], "/batch/submit", 200, latency, ip, fn or ""
                )
                logger.info(
                    f"Batch job done | job_id={jid} | latency={round(latency, 2)}ms"
                )
                await fire_webhook(key_info["key"], jid, scored)
            except Exception as e:
                jobs[jid].update({"status": "failed", "error": str(e)})
                logger.error(f"Batch job failed | job_id={jid} | file={fn} | error={e}")

        background_tasks.add_task(process)

    return {
        "batch_id": batch_id,
        "total_files": len(files),
        "job_ids": job_ids,
        "poll_urls": [f"/jobs/{jid}" for jid in job_ids],
    }


# ─── Webhook Management ───────────────────────────────────────
@app.post("/webhooks")
def register_webhook(url: str, x_api_key: Optional[str] = Header(None)):
    key_info = verify_key(x_api_key)
    conn = get_db()
    conn.execute(
        "INSERT INTO webhooks (api_key, url) VALUES (?, ?)", (key_info["key"], url)
    )
    conn.commit()
    conn.close()
    logger.info(f"Webhook registered | url={url} | key={key_info['key'][:12]}...")
    return {"message": "Webhook registered", "url": url}


@app.get("/webhooks")
def list_webhooks(x_api_key: Optional[str] = Header(None)):
    key_info = verify_key(x_api_key)
    conn = get_db()
    rows = conn.execute(
        "SELECT id, url, is_active, created_at FROM webhooks WHERE api_key = ?",
        (key_info["key"],),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.delete("/webhooks/{webhook_id}")
def delete_webhook(webhook_id: int, x_api_key: Optional[str] = Header(None)):
    key_info = verify_key(x_api_key)
    conn = get_db()
    conn.execute(
        "UPDATE webhooks SET is_active = 0 WHERE id = ? AND api_key = ?",
        (webhook_id, key_info["key"]),
    )
    conn.commit()
    conn.close()
    logger.info(f"Webhook removed | id={webhook_id} | key={key_info['key'][:12]}...")
    return {"message": "Webhook removed"}


# ─── Admin Routes ─────────────────────────────────────────────
@app.post("/admin/keys")
def create_key(
    name: str,
    tier: Tier = Tier.FREE,
    expires_days: Optional[int] = None,
    x_api_key: Optional[str] = Header(None),
):
    require_admin(x_api_key)
    limits = TIER_LIMITS[tier]
    new_key = f"{tier.value}-" + secrets.token_hex(20)
    expires_at = (
        (datetime.now() + timedelta(days=expires_days)).isoformat()
        if expires_days
        else None
    )

    conn = get_db()
    conn.execute(
        "INSERT INTO api_keys (key, name, tier, rpm_limit, rpd_limit, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
        (new_key, name, tier.value, limits["rpm"], limits["rpd"], expires_at),
    )
    conn.commit()
    conn.close()
    logger.info(
        f"API key created | name={name} | tier={tier.value} | expires={expires_at}"
    )
    return {
        "key": new_key,
        "name": name,
        "tier": tier,
        "rpm": limits["rpm"],
        "rpd": limits["rpd"],
        "expires_at": expires_at,
    }


@app.get("/admin/keys")
def list_keys(x_api_key: Optional[str] = Header(None)):
    require_admin(x_api_key)
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, key, tier, is_active, rpm_limit, rpd_limit, expires_at, created_at FROM api_keys"
    ).fetchall()
    conn.close()
    logger.info("Admin listed all API keys")
    return [dict(r) for r in rows]


@app.patch("/admin/keys/{key_id}")
def update_key(
    key_id: int,
    is_active: Optional[int] = None,
    tier: Optional[Tier] = None,
    x_api_key: Optional[str] = Header(None),
):
    require_admin(x_api_key)
    conn = get_db()
    if is_active is not None:
        conn.execute(
            "UPDATE api_keys SET is_active = ? WHERE id = ?", (is_active, key_id)
        )
        logger.info(f"Key updated | id={key_id} | is_active={is_active}")
    if tier is not None:
        limits = TIER_LIMITS[tier]
        conn.execute(
            "UPDATE api_keys SET tier = ?, rpm_limit = ?, rpd_limit = ? WHERE id = ?",
            (tier.value, limits["rpm"], limits["rpd"], key_id),
        )
        logger.info(f"Key updated | id={key_id} | tier={tier.value}")
    conn.commit()
    conn.close()
    return {"message": f"Key {key_id} updated"}


@app.delete("/admin/keys/{key_id}")
def revoke_key(key_id: int, x_api_key: Optional[str] = Header(None)):
    require_admin(x_api_key)
    conn = get_db()
    conn.execute("UPDATE api_keys SET is_active = 0 WHERE id = ?", (key_id,))
    conn.commit()
    conn.close()
    logger.info(f"Key revoked | id={key_id}")
    return {"message": f"Key {key_id} revoked"}


@app.get("/admin/usage")
def usage_stats(x_api_key: Optional[str] = Header(None)):
    require_admin(x_api_key)
    conn = get_db()
    stats = conn.execute("""
        SELECT
            u.api_key,
            k.name,
            k.tier,
            COUNT(*) as total_requests,
            SUM(CASE WHEN u.status = 200 THEN 1 ELSE 0 END) as success,
            SUM(CASE WHEN u.status != 200 THEN 1 ELSE 0 END) as errors,
            ROUND(AVG(u.latency_ms), 2) as avg_latency_ms,
            ROUND(MIN(u.latency_ms), 2) as min_latency_ms,
            ROUND(MAX(u.latency_ms), 2) as max_latency_ms,
            MAX(u.timestamp) as last_used
        FROM usage_logs u
        LEFT JOIN api_keys k ON u.api_key = k.key
        GROUP BY u.api_key
        ORDER BY total_requests DESC
    """).fetchall()

    today_stats = conn.execute("""
        SELECT COUNT(*) as today_total,
               SUM(CASE WHEN status = 200 THEN 1 ELSE 0 END) as today_success
        FROM usage_logs
        WHERE DATE(timestamp) = DATE('now')
    """).fetchone()

    conn.close()
    logger.info("Admin fetched usage stats")
    return {
        "today": dict(today_stats),
        "by_key": [dict(r) for r in stats],
    }


@app.get("/admin/logs")
def recent_logs(limit: int = 50, x_api_key: Optional[str] = Header(None)):
    require_admin(x_api_key)
    conn = get_db()
    rows = conn.execute(
        """
        SELECT u.*, k.name, k.tier
        FROM usage_logs u
        LEFT JOIN api_keys k ON u.api_key = k.key
        ORDER BY u.timestamp DESC
        LIMIT ?
    """,
        (limit,),
    ).fetchall()
    conn.close()
    logger.info(f"Admin fetched last {limit} logs")
    return [dict(r) for r in rows]


@app.get("/")
def home():
    return {
        "name": "Invoice Parser API",
        "version": "2.0.0",
        "status": "running ✅",
        "device": device,
        "endpoints": {
            "sync": "POST /parse-invoice",
            "async": "POST /jobs/submit → GET /jobs/{id}",
            "batch": "POST /batch/submit",
            "webhooks": "POST /webhooks",
            "health": "GET /health",
            "docs": "GET /docs",
        },
        "tiers": {t.value: TIER_LIMITS[t] for t in Tier},
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
