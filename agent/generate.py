import os
import logging
import asyncio
from datetime import datetime, timezone
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# --- Dry-run mode ---
# Set PATCHNOTE_DRY_RUN=true in .env to skip all API calls.
# The full pipeline runs but generation returns placeholder text.
DRY_RUN = os.environ.get("PATCHNOTE_DRY_RUN", "false").lower() == "true"

# --- Global generation budget ---
# Hard ceiling on API calls per day regardless of who triggers them.
# Change PATCHNOTE_DAILY_BUDGET in .env to adjust. Default is 20 calls/day.
DAILY_BUDGET = int(os.environ.get("PATCHNOTE_DAILY_BUDGET", "20"))

_budget_lock = asyncio.Lock()
_calls_today = 0
_budget_date = datetime.now(timezone.utc).date()

async def _check_and_consume_budget() -> bool:
    """Returns True if a call is allowed, False if the daily budget is exhausted."""
    global _calls_today, _budget_date

    async with _budget_lock:
        today = datetime.now(timezone.utc).date()

        #Reset counter at midnight UTC
        if today != _budget_date:
            _calls_today = 0
            _budget_date = today
        
        if _calls_today >= DAILY_BUDGET:
            return False
        
        _calls_today += 1
        return True
    
def get_budget_status() -> dict:
    """Return current budget usage for logging or status checks."""
    return {
        "calls_today": _calls_today,
        "daily_budget": DAILY_BUDGET,
        "remaining": max(0, DAILY_BUDGET - _calls_today),
        "dry_run": DRY_RUN,
    }

GENERATION_SYSTEM_PROMPT = """\
You are a technical writer generating release notes for a software team.
You will be given raw data from merged pull requests and a specific audience to write for.
Write clearly, concisely, and in the register appropriate for that audience.
Do not add preamble. Start your response directly with the release summary line.
"""

async def generate_release_notes(
    raw_data: str,
    audience_prompt: str,
    repo: str,
    audience: str = "unknown",
) -> str:
    """Generate audience-specific release notes from raw PR data.
    
    Respects dry-run mode and daily budget before calling the API.
    """

    # Dry-run short-circuit, no API call, no cost
    if DRY_RUN:
        logger.info(f"[DRY RUN] Skipping generation for {audience} audience ({repo})")
        return(
            f"[DRY RUN] {audience.upper()} release notes for *{repo}*\n\n"
            f"This is placeholder text. Set PATCHNOTE_DRY_RUN=false to generate real notes.\n\n"
            f"• Change 1: Example engineering change\n"
            f"• Change 2: Another example change\n"
            f"• Change 3: A third example change"
        )
    
    #Budget check - refuse if daily cap is hit
    allowed = await _check_and_consume_budget()
    if not allowed:
        status = get_budget_status()
        logger.warning(
            f"Daily generation budget exhausted ({status['calls_today']}/{status['daily_budget']}). "
            f"Skipping {audience} generation for {repo}."
        )
        return(
            f":warning: Daily generation budget exhausted "
            f"({status['calls_today']}/{status['daily_budget']} calls used). "
            f"Try again tomorrow or increase PATCHNOTE_DAILY_BUDGET."
        )
    
    status = get_budget_status()
    logger.info(
        f"Generating {audience} notes for {repo} "
        f"(budget: {status['calls_today']}/{status['daily_budget']})"
    )

    try:
        message = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=GENERATION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content":(
                        f"{audience_prompt}\n\n"
                        f"---\n\n"
                        f"Here is the raw PR data for {repo}:\n\n"
                        f"{raw_data}"
                    )
                }
            ]
        )
        return message.content[0].text
    except Exception as e:
        logger.exception(f"Generation failed for {audience} ({repo}) : {e}")
        return f"(Generation failed : {e})"