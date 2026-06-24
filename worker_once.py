import asyncio
import logging
from worker import scan_repos, process_repo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_once():
    """Run a single pass: check all repos with active batches and process
    any whose merge window has expired. Designed to be triggered by a
    scheduled cron job rather than running as a continuous loop.
    """
    logger.info("Cron-triggered worker run starting")

    try:
        repos = await scan_repos()
        if repos:
            logger.info(f"Found active batches for: {repos}")
            await asyncio.gather(*[process_repo(repo) for repo in repos])
        else:
            logger.info("No active batches found")
    except Exception as e:
        logger.exception(f"Worker run failed: {e}")

    logger.info("Cron-triggered worker run complete")


if __name__ == "__main__":
    asyncio.run(run_once())