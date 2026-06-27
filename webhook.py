import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Header, HTTPException, Request
from upstash_redis.asyncio import Redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

redis = Redis(
    url=os.environ.get("UPSTASH_REDIS_REST_URL"),
    token=os.environ.get("UPSTASH_REDIS_REST_TOKEN"),
)

GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
MERGE_WINDOW_SECONDS = int(os.environ.get("PATCHNOTE_MERGE_WINDOW", "60"))


def verify_github_signature(payload: bytes, signature: str) -> bool:
    """Verify the webhook came from GitHub and not a random sender."""
    if not GITHUB_WEBHOOK_SECRET:
        logger.warning("No GITHUB_WEBHOOK_SECRET set — skipping signature verification")
        return True

    mac = hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    )
    expected = "sha256=" + mac.hexdigest()

    return hmac.compare_digest(expected, signature)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "patchnote-webhook"}


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(None),
    x_hub_signature_256: str = Header(None),
):
    payload_bytes = await request.body()

    # Verify signature
    if x_hub_signature_256:
        if not verify_github_signature(payload_bytes, x_hub_signature_256):
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Only care about pull_request events
    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": f"event type {x_github_event} not handled"}

    payload = json.loads(payload_bytes)

    # Only care about merged PRs
    action = payload.get("action")
    pr = payload.get("pull_request", {})
    merged = pr.get("merged", False)

    if action != "closed" or not merged:
        return {"status": "ignored", "reason": "PR not merged"}

    repo = payload.get("repository", {}).get("full_name")
    pr_number = pr.get("number")
    pr_title = pr.get("title")
    merged_at = pr.get("merged_at")

    if not repo:
        raise HTTPException(status_code=400, detail="Missing repository info")

    logger.info(f"Merged PR received: {repo}#{pr_number} — {pr_title}")

    # Idempotency check — skip if we already queued this PR
    idempotency_key = f"patchnote:seen:{repo}:{pr_number}"
    already_seen = await redis.get(idempotency_key)
    if already_seen:
        logger.info(f"Duplicate webhook for {repo}#{pr_number} — skipping")
        return {"status": "ignored", "reason": "duplicate"}

    # Mark as seen for 24 hours
    await redis.set(idempotency_key, "1", ex=86400)

    # Add PR to the merge window batch for this repo
    batch_key = f"patchnote:batch:{repo}"
    job_data = json.dumps({
        "repo": repo,
        "pr_number": pr_number,
        "pr_title": pr_title,
        "merged_at": merged_at,
        "queued_at": time.time(),
    })
    await redis.rpush(batch_key, job_data)

    # Set a window expiry key if not already set
    # This tells the worker when to process the batch
    window_key = f"patchnote:window:{repo}"
    window_exists = await redis.get(window_key)
    if not window_exists:
        await redis.set(window_key, time.time(), ex=MERGE_WINDOW_SECONDS)
        logger.info(f"Merge window opened for {repo} ({MERGE_WINDOW_SECONDS}s)")

    return {
        "status": "queued",
        "repo": repo,
        "pr_number": pr_number,
    }

@app.get("/api/changelog/{owner}/{repo}")
async def get_changelog(owner: str, repo: str):
    """Public endpoint returning approved release notes for a repo, using the product-audience note as the default public-facing text."""
    from db.database import AsyncSessionLocal, init_db
    from sqlalchemy import select
    from db.models import Release, ReleaseNote, AudienceType, ApprovalStatus

    await init_db()

    full_repo = f"{owner}/{repo}"

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Release)
            .where(Release.repo == full_repo)
            .order_by(Release.created_at.desc())
            .limit(50)
        )
        releases = result.scalars().all()

        entries = []
        for release in releases:
            note_result = await session.execute(
                select(ReleaseNote)
                .where(ReleaseNote.release_id == release.id)
                .where(ReleaseNote.audience == AudienceType.product)
                .where(ReleaseNote.status == ApprovalStatus.approved)
            )
            note = note_result.scalar_one_or_none()

            if note:
                entries.append({
                    "release_id": str(release.id),
                    "date": release.created_at.isoformat(),
                    "pr_count": len(release.pr_numbers.split(",")),
                    "content": note.content,
                })
    return {"repo": full_repo, "entries": entries}