import asyncio
import sys
from dotenv import load_dotenv

load_dotenv()

from db.database import AsyncSessionLocal, init_db
from db.crud import add_tracked_repo, get_tracked_repos


async def main():
    await init_db()

    async with AsyncSessionLocal() as session:
        existing = await get_tracked_repos(session)
        print("Currently tracked repos:")
        for r in existing:
            print(f"  {r.repo} ({r.display_name})")

        if len(sys.argv) == 3:
            repo, display_name = sys.argv[1], sys.argv[2]
            tracked = await add_tracked_repo(session, repo, display_name)
            print(f"\nAdded: {tracked.repo} ({tracked.display_name})")
        else:
            print("\nUsage: python3 register_repo.py owner/repo \"Display Name\"")


asyncio.run(main())