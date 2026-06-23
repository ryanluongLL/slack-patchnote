import asyncio
import json
import logging
import os
import time

from dotenv import load_dotenv

load_dotenv()

from upstash_redis.asyncio import Redis
from slack_sdk.web.async_client import AsyncWebClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

redis = Redis(
    url=os.environ.get("UPSTASH_REDIS_REST_URL"),
    token=os.environ.get("UPSTASH_REDIS_REST_TOKEN"),
)

slack_client = AsyncWebClient(token=os.environ.get("SLACK_BOT_TOKEN"))

POLL_INTERVAL = int(os.environ.get("PATCHNOTE_POLL_INTERVAL", "10"))
MAX_RETRIES = int(os.environ.get("PATCHNOTE_MAX_RETRIES", "3"))


async def process_batch(repo: str, jobs: list[dict]):
    """Process a batch of merged PRs for one repo and generate notes."""
    from listeners.commands.patchnote_command import (
        _fetch_pr_data_structured,
        AUDIENCES,
        ENGINEERING_CHANNEL,
    )
    from agent.generate import get_budget_status, generate_release_notes
    from agent.embeddings import build_pr_summary_text, embed_pr_summary
    from db.database import AsyncSessionLocal, init_db
    from db.crud import create_release, create_release_note, create_pr_embedding
    from db.models import AudienceType

    await init_db()

    pr_list = ", ".join(f"#{j['pr_number']} {j['pr_title']}" for j in jobs)
    logger.info(f"Processing batch for {repo}: {pr_list}")

    status = get_budget_status()
    if status["remaining"] == 0 and not status["dry_run"]:
        logger.warning(f"Budget exhausted, skipping batch for {repo}")
        await slack_client.chat_postMessage(
            channel=ENGINEERING_CHANNEL,
            text=f":warning: PatchNote budget exhausted. Skipped batch for *{repo}* ({len(jobs)} PRs).",
        )
        return

    pr_records, raw_data = await _fetch_pr_data_structured(repo)

    if not raw_data or "GitHub API error" in raw_data:
        logger.error(f"Failed to fetch PR data for {repo}: {raw_data}")
        return

    # Persist the release first
    async with AsyncSessionLocal() as session:
        release = await create_release(
            session=session,
            repo=repo,
            pr_numbers=[j["pr_number"] for j in jobs],
            pr_titles=[j["pr_title"] for j in jobs],
            raw_data=raw_data,
            triggered_by="webhook",
        )
        logger.info(f"Release {release.id} created for {repo}")

    # Embed each PR individually for future similarity and clustering
    embedding_list = []
    for pr in pr_records:
        try:
            summary_text = build_pr_summary_text(
                pr_number=pr["pr_number"],
                pr_title=pr["pr_title"],
                details_text=pr["details_text"],
                diff_text=pr["diff_text"],
            )
            embedding = await embed_pr_summary(summary_text)
            embedding_list.append(embedding)

            async with AsyncSessionLocal() as session:
                await create_pr_embedding(
                    session=session,
                    release_id=release.id,
                    repo=repo,
                    pr_number=pr["pr_number"],
                    pr_title=pr["pr_title"],
                    summary_text=summary_text,
                    embedding=embedding,
                )
            logger.info(f"Embedded PR #{pr['pr_number']} for release {release.id}")
        except Exception as e:
            logger.exception(f"Failed to embed PR #{pr['pr_number']}: {e}")
            embedding_list.append(None)
            # Don't fail the whole batch if one embedding fails
        

    #Cluster related PRs and build a smarter generation input
    generation_text = raw_data #fallback to flatterned text
    valid_pairs = [(pr, emb) for pr, emb in zip(pr_records, embedding_list) if emb is not None]


    if len(valid_pairs) >= 2:
        try:
            from agent.clustering import cluster_prs, format_clusters_for_prompt

            valid_records = [p for p, _ in valid_pairs]
            valid_embeddings = [e for _, e in valid_pairs]

            clusters = await cluster_prs(valid_records, valid_embeddings)
            generation_text = format_clusters_for_prompt(valid_records, clusters)
            logger.info(f"Clustered {len(pr_records)} PRs into {len(clusters)} groups")
        except Exception as e:
            logger.exception(f"Clustering failed, falling back to flat text:")
    #Post trigger message
    await slack_client.chat_postMessage(
        channel=ENGINEERING_CHANNEL,
        text=(
            f":gear: Auto-generating PatchNotes for *{repo}*\n"
            f"Triggered by {len(jobs)} merged PR(s): {pr_list}"
        ),
    )

    #Generated and persist notes for all three audiences
    for audience, channel, system_prompt, emoji in AUDIENCES:
        response_text = await generate_release_notes(
            raw_data=generation_text,
            audience_prompt=system_prompt,
            repo=repo,
            audience=audience
        )

        msg = await slack_client.chat_postMessage(
            channel=channel,
            text=f"{emoji} *PatchNote for {repo}*\n\n{response_text}",
        )

        async with AsyncSessionLocal() as session:
            await create_release_note(
                session=session,
                release_id=release.id,
                audience=AudienceType(audience),
                content=response_text,
                slack_channel_id=channel,
                slack_message_ts=msg["ts"],
            )
            logger.info(f"Persisted {audience} note for release {release.id}")
    logger.info(f"Batch complete for {repo}")


async def process_repo(repo: str):
    """Check if a repo's merge window has expired and process its batch."""
    window_key = f"patchnote:window:{repo}"
    batch_key = f"patchnote:batch:{repo}"
    retry_key = f"patchnote:retry:{repo}"

    window = await redis.get(window_key)
    if window:
        # Window still open, not time to process yet
        return

    # Window expired, pull all jobs from the batch
    raw_jobs = await redis.lrange(batch_key, 0, -1)
    if not raw_jobs:
        return

    # Clear the batch immediately to avoid double processing
    await redis.delete(batch_key)

    jobs = []
    for raw in raw_jobs:
        try:
            jobs.append(json.loads(raw))
        except json.JSONDecodeError:
            logger.warning(f"Skipping malformed job: {raw}")

    if not jobs:
        return

    # Retry tracking
    retries = int(await redis.get(retry_key) or 0)

    try:
        await process_batch(repo, jobs)
        await redis.delete(retry_key)
    except Exception as e:
        logger.exception(f"Batch processing failed for {repo}: {e}")
        retries += 1

        if retries < MAX_RETRIES:
            logger.info(f"Requeueing batch for {repo} (attempt {retries}/{MAX_RETRIES})")
            # Put jobs back in the queue
            for job in jobs:
                await redis.rpush(batch_key, json.dumps(job))
            # Reopen window for 30 seconds before retry
            await redis.set(window_key, time.time(), ex=30)
            await redis.set(retry_key, retries, ex=3600)
        else:
            logger.error(f"Max retries exceeded for {repo}, dropping batch")
            await redis.delete(retry_key)


async def scan_repos() -> list[str]:
    """Find all repos that have active batches or expired windows."""
    batch_keys = await redis.keys("patchnote:batch:*")
    repos = set()
    for key in batch_keys:
        repo = key.replace("patchnote:batch:", "")
        repos.add(repo)
    return list(repos)


async def run_worker():
    """Main worker loop. Polls Redis every POLL_INTERVAL seconds."""
    logger.info(f"Worker started. Polling every {POLL_INTERVAL}s.")

    while True:
        try:
            repos = await scan_repos()
            if repos:
                logger.info(f"Found active batches for: {repos}")
                await asyncio.gather(*[process_repo(repo) for repo in repos])
        except Exception as e:
            logger.exception(f"Worker loop error: {e}")

        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run_worker())