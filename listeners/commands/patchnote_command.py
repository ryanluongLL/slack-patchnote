import asyncio
from logging import Logger

from slack_bolt.context.ack.async_ack import AsyncAck
from slack_bolt.context.respond.async_respond import AsyncRespond
from slack_sdk.web.async_client import AsyncWebClient

from agent import AgentDeps, run_agent

async def handle_patchnote_command(
    ack: AsyncAck,
    body: dict,
    client: AsyncWebClient,
    respond: AsyncRespond,
    logger: Logger,
):
    # Acknowledge immediately — Slack requires a response within 3 seconds
    await ack()

    text = (body.get("text") or "").strip()

    if not text.startswith("ship "):
        await respond(
            "Usage: `/patchnote ship <owner/repo>`\n"
            "Example: `/patchnote ship ryanluongLL/slack-patchnote`"
        )
        return
    
    repo = text.replace("ship ", "", 1).strip()
    channel_id = body["channel_id"]
    user_id = body["user_id"]

    # Post a status message so the user knows work is happening
    status_msg = await client.chat_postMessage(
        channel=channel_id,
        text=f":gear: Generating PatchNotes for *{repo}*... this may take a moment.",
    )
    thread_ts = status_msg["ts"]

    # Run the agent async so we dont block
    asyncio.create_task(
        _run_patchnote(
            repo=repo,
            channel_id=channel_id,
            thread_ts=thread_ts,
            user_id=user_id,
            client=client,
            logger=logger,
        )
    )

async def _run_patchnote(
        repo: str,
        channel_id: str,
        thread_ts: str,
        user_id: str,
        client: AsyncWebClient,
        logger: Logger
): 
    try:
        prompt = (
            f"Use get_recent_prs to fetch the last 5 merged PRs for {repo}. "
            f"Then for each PR, use get_pr_details and get_pr_diff to understand what changed. "
            f"Summarize what you found: list each PR title, what files changed, "
            f"and any linked issues. Keep it factual for now."
        )

        deps = AgentDeps(
            client=client,
            user_id=user_id,
            channel_id=channel_id,
            thread_ts=thread_ts,
            message_ts=thread_ts,
            user_token=None,
        )

        response_text, _ = await run_agent(prompt, deps=deps)

        await client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=response_text,
        )
    
    except Exception as e:
        logger.exception(f"PatchNote command failed: {e}")
        await client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=f":warning: Something went wrong: {e}",
        )