# PatchNote

PatchNote watches a GitHub repository for merged pull requests and automatically generates three audience-specific release notes, one for engineering, one for product, and one for support, then posts each to its own dedicated Slack channel. No manual writing, no waiting on someone to remember to update the team.

A new merge on GitHub triggers a fully autonomous pipeline: the change is fetched, embedded, clustered with related changes, written in three different voices, persisted, and delivered, all without a human in the loop.

## Why this exists

Every team that ships software has the same gap after a release: engineers know what changed at the code level, but product, support, and leadership rarely get a clear, timely translation of that change into terms that matter to them. PatchNote closes that gap automatically, using the actual diff and PR context, not just the PR title.

## What it does

1. A pull request gets merged on a watched GitHub repository.
2. GitHub sends a webhook to PatchNote's receiver.
3. The merge is added to a short batching window so multiple PRs merged close together get summarized together instead of spamming separate messages.
4. Once the window closes, the system fetches the PR's title, description, labels, linked issues, and diff directly from GitHub.
5. Each PR is embedded into a vector and compared against the others in the batch. Related changes are clustered together so the writer treats them as one theme rather than disconnected bullet points.
6. Claude generates three different documents from the same source material:
   - **Engineering**: technical changelog, breaking changes, migration notes
   - **Product**: plain-English feature narrative for stakeholders
   - **Support**: customer-facing talking points and known limitations
7. Every release and its three notes are persisted to Postgres.
8. The three notes are posted to their own Slack channels automatically.

A manual `/patchnote ship <owner/repo>` slash command is also available as an on-demand override for testing or ad hoc use.

## Architecture

```
GitHub (merge event)
       |
       v
Webhook Receiver (FastAPI, Render)
  - verifies GitHub signature
  - checks idempotency
  - opens a merge window
       |
       v
Redis Queue (Upstash)
  - holds batched PR jobs per repo
       |
       v
Worker (Render Cron, every 2 min)
  - polls for expired merge windows
  - fetches PR data from GitHub API
       |
       +---> Voyage AI: embeds each PR, clusters related changes
       |
       +---> Claude API: generates 3 audience-specific notes
       |
       +---> Neon Postgres (pgvector): persists release, notes, embeddings
       |
       +---> Slack (Bolt + Claude Agent SDK): posts notes to 3 channels
```

## Tech stack

| Layer | Technology |
|---|---|
| Slack integration | Slack Bolt for Python, Claude Agent SDK, custom MCP tools |
| Webhook receiver | FastAPI, deployed on Render (Web Service) |
| Queue / batching | Upstash Redis (REST API, async client) |
| Background processing | Render Cron Job, polling on a 2-minute schedule |
| GitHub integration | GitHub REST API via custom async tools (`get_recent_prs`, `get_pr_details`, `get_pr_diff`) |
| Embeddings | Voyage AI, `voyage-4-lite`, 512-dimension vectors |
| Clustering | Cosine similarity, single-link clustering, threshold 0.80 |
| Generation | Anthropic Claude API, direct single-shot calls (Haiku for development, Sonnet for production-quality output) |
| Persistence | Neon Postgres with the `pgvector` extension, SQLAlchemy async ORM |
| Reliability | Idempotency keys (24hr TTL), retry with requeue (max 3 attempts), daily generation budget cap, dry-run mode |

## Key design decisions

**Agent SDK only where reasoning is needed.** The GitHub data-gathering step uses the Claude Agent SDK with custom MCP tools because the agent genuinely decides which tool to call and when. The three generation steps use plain, single-shot Anthropic API calls instead, since writing audience-specific notes from already-gathered data is not an agentic task. This split cut token usage and cost substantially compared to wrapping every step in the agent loop.

**Embeddings and clustering are functional, not decorative.** A batch of several merged PRs is embedded individually, then PRs above a similarity threshold are grouped before generation. This means a release with three commits to the same feature gets summarized as one coherent theme instead of three disconnected bullet points.

**Cron over a long-running worker.** Render's free tier no longer supports always-on background workers, so the worker was restructured to run a single pass and exit, triggered by a scheduled cron job. This is a legitimate, low-cost pattern for batch-style background processing and avoids paying for an idle, always-on process.

**Merge window batching.** Triggering one note per individual PR merge would spam channels. PRs merged within a short window of each other are batched into a single digest per audience.

**No user accounts or authentication.** The system has no login and stores no personal data, since the only identities involved are the Slack workspace (already authenticated by Slack itself) and a GitHub repository.

**Cost guardrails.** A `PATCHNOTE_DRY_RUN` flag skips all model calls and returns placeholder text, allowing the entire pipeline, webhook, queue, batching, clustering, and Slack delivery, to be exercised and tested for free. A `PATCHNOTE_DAILY_BUDGET` enforces a hard cap on generation calls per day regardless of trigger volume.

## Local development

Three processes run concurrently during local development:

```bash
# Terminal 1: the Slack Bolt app (Socket Mode)
slack run

# Terminal 2: the worker, continuous polling loop
python3 worker.py

# Terminal 3: the webhook receiver
uvicorn webhook:app --reload --port 8080
```

Simulate a GitHub webhook locally with:

```bash
curl -X POST http://localhost:8080/webhook/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -d '{
    "action": "closed",
    "pull_request": {
      "number": 1,
      "title": "Example PR",
      "merged": true,
      "merged_at": "2026-01-01T00:00:00Z"
    },
    "repository": { "full_name": "owner/repo" }
  }'
```

## Deployment

- **Webhook receiver**: Render Web Service, `uvicorn webhook:app --host 0.0.0.0 --port $PORT`
- **Worker**: Render Cron Job, `python3 worker_once.py`, scheduled every 2 minutes
- **Slack app**: currently run via Socket Mode locally for development; production deployment is a future step

## Environment variables

```
ANTHROPIC_API_KEY
GITHUB_TOKEN
GITHUB_WEBHOOK_SECRET
SLACK_BOT_TOKEN
SLACK_APP_TOKEN
VOYAGE_API_KEY
UPSTASH_REDIS_REST_URL
UPSTASH_REDIS_REST_TOKEN
DATABASE_URL
PATCHNOTE_ENGINEERING_CHANNEL
PATCHNOTE_PRODUCT_CHANNEL
PATCHNOTE_SUPPORT_CHANNEL
PATCHNOTE_MERGE_WINDOW
PATCHNOTE_DRY_RUN
PATCHNOTE_DAILY_BUDGET
PATCHNOTE_POLL_INTERVAL
PATCHNOTE_MAX_RETRIES
```

## Status

The full pipeline (webhook ingestion, queueing, merge-window batching, GitHub data fetch, embedding, clustering, three-audience generation, persistence, and Slack delivery) is deployed and confirmed working end to end against real public repositories. Remaining work includes a feedback loop that uses approve/reject signals from Slack to improve note routing over time, and a public-facing changelog frontend.
