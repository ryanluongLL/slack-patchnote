import asyncio
import os
from logging import Logger

from slack_bolt.context.ack.async_ack import AsyncAck
from slack_bolt.context.respond.async_respond import AsyncRespond
from slack_sdk.web.async_client import AsyncWebClient

from agent import AgentDeps, run_agent
from agent.prompts import ENGINEERING_PROMPT, PRODUCT_PROMPT, SUPPORT_PROMPT

from agent.generate import generate_release_notes

# Channel IDs or names for each audience
# Using channel names — Slack resolves them automatically
ENGINEERING_CHANNEL = os.environ.get("PATCHNOTE_ENGINEERING_CHANNEL", "patchnote-engineering")
PRODUCT_CHANNEL = os.environ.get("PATCHNOTE_PRODUCT_CHANNEL", "patchnote-product")
SUPPORT_CHANNEL = os.environ.get("PATCHNOTE_SUPPORT_CHANNEL", "patchnote-support")

AUDIENCES = [
    ("engineering", ENGINEERING_CHANNEL, ENGINEERING_PROMPT, ":hammer_and_wrench:"),
    ("product", PRODUCT_CHANNEL, PRODUCT_PROMPT, ":bar_chart:"),
    ("support", SUPPORT_CHANNEL, SUPPORT_PROMPT, ":headphones:"),
]


async def handle_patchnote_command(
    ack: AsyncAck,
    body: dict,
    client: AsyncWebClient,
    respond: AsyncRespond,
    logger: Logger,
):
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

    status_msg = await client.chat_postMessage(
        channel=channel_id,
        text=(
            f":gear: Generating PatchNotes for *{repo}*...\n"
            f"Posting to <#{ENGINEERING_CHANNEL}>, <#{PRODUCT_CHANNEL}>, and <#{SUPPORT_CHANNEL}> shortly."
        ),
    )
    thread_ts = status_msg["ts"]

    asyncio.create_task(
        _run_patchnote_pipeline(
            repo=repo,
            trigger_channel_id=channel_id,
            trigger_thread_ts=thread_ts,
            user_id=user_id,
            client=client,
            logger=logger,
        )
    )


# async def _fetch_pr_data(repo: str, user_id: str, client: AsyncWebClient) -> str:
#     """Run one agent call to gather all raw PR data for the repo."""
#     gather_prompt = (
#         f"Use get_recent_prs to fetch the last 5 merged PRs for {repo}. "
#         f"Then for each PR, call get_pr_details and get_pr_diff. "
#         f"Return a comprehensive structured summary of everything you found: "
#         f"PR numbers, titles, merged dates, labels, linked issues, changed files, "
#         f"and the key diff content for each PR. Be thorough — this data will be used "
#         f"to generate release notes for three different audiences."
#     )

#     # Use a throwaway channel for data gathering — we only care about the text
#     deps = AgentDeps(
#         client=client,
#         user_id=user_id,
#         channel_id="",
#         thread_ts="",
#         message_ts="",
#         user_token=None,
#     )

#     raw_data, _ = await run_agent(gather_prompt, deps=deps)
#     return raw_data

async def _fetch_pr_data(repo: str, user_id: str, client: AsyncWebClient) -> str:
    """Fetch PR data directly using GitHub tools, no agent loop needed."""
    from agent.tools.github_prs import get_recent_prs_tool, get_pr_details_tool, get_pr_diff_tool

    results = []

    # Step 1: get recent PRs
    prs_result = await get_recent_prs_tool.handler({"repo": repo, "limit": 3})
    prs_text = prs_result["content"][0]["text"]

    if "No merged PRs" in prs_text or "GitHub API error" in prs_text:
        return prs_text

    results.append(f"=== MERGED PRs ===\n{prs_text}")

    # Step 2: extract PR numbers from the text
    import re
    pr_numbers = re.findall(r"PR #(\d+):", prs_text)

    # Step 3: fetch details and diff for each PR
    for pr_num in pr_numbers:
        pr_number = int(pr_num)

        details_result = await get_pr_details_tool.handler({"repo": repo, "pr_number": pr_number})
        details_text = details_result["content"][0]["text"]
        results.append(f"=== PR #{pr_number} DETAILS ===\n{details_text}")

        diff_result = await get_pr_diff_tool.handler({"repo": repo, "pr_number": pr_number})
        diff_text = diff_result["content"][0]["text"]
        results.append(f"=== PR #{pr_number} DIFF ===\n{diff_text}")

    return "\n\n".join(results)



async def _generate_for_audience(
    raw_data: str,
    audience: str,
    channel: str,
    system_prompt: str,
    emoji: str,
    repo: str,
    user_id: str,
    client: AsyncWebClient,
    logger: Logger,
):
    try:
        response_text = await generate_release_notes(
            raw_data=raw_data,
            audience_prompt=system_prompt,
            repo=repo,
            audience=audience
        )

        await client.chat_postMessage(
            channel=channel,
            text=f"{emoji} *PatchNote for {repo}*\n\n{response_text}",
        )
        logger.info(f"Posted {audience} notes to #{channel}")

    except Exception as e:
        logger.exception(f"Failed to generate {audience} notes: {e}")


async def _run_patchnote_pipeline(
    repo: str,
    trigger_channel_id: str,
    trigger_thread_ts: str,
    user_id: str,
    client: AsyncWebClient,
    logger: Logger,
):
    try:
        # Step 1: Gather all PR data once
        logger.info(f"Fetching PR data for {repo}")
        raw_data = await _fetch_pr_data(repo, user_id, client)

        if not raw_data:
            await client.chat_postMessage(
                channel=trigger_channel_id,
                thread_ts=trigger_thread_ts,
                text=":warning: Could not fetch PR data. Check the repo name and try again.",
            )
            return

        # Step 2: Generate all three versions in parallel
        logger.info("Generating notes for all three audiences in parallel")
        for audience, channel, system_prompt, emoji in AUDIENCES:
            await _generate_for_audience(
                raw_data=raw_data,
                audience=audience,
                channel=channel,
                system_prompt=system_prompt,
                emoji=emoji,
                repo=repo,
                user_id=user_id,
                client=client,
                logger=logger,
            )

        # Step 3: Post a completion summary in the trigger thread
        await client.chat_postMessage(
            channel=trigger_channel_id,
            thread_ts=trigger_thread_ts,
            text=(
                f":white_check_mark: PatchNotes for *{repo}* posted to all channels.\n"
                f":hammer_and_wrench: <#{ENGINEERING_CHANNEL}> "
                f":bar_chart: <#{PRODUCT_CHANNEL}> "
                f":headphones: <#{SUPPORT_CHANNEL}>"
            ),
        )

    except Exception as e:
        logger.exception(f"PatchNote pipeline failed: {e}")
        await client.chat_postMessage(
            channel=trigger_channel_id,
            thread_ts=trigger_thread_ts,
            text=f":warning: Pipeline failed: {e}",
        )