import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from agent.tools.github_prs import get_recent_prs_tool, get_pr_details_tool, get_pr_diff_tool
import re


async def test_fetch(repo: str):
    print(f"Fetching PRs for {repo}...\n")

    prs_result = await get_recent_prs_tool.handler({"repo": repo, "limit": 3})
    prs_text = prs_result["content"][0]["text"]
    print("=== MERGED PRs ===")
    print(prs_text)

    pr_numbers = re.findall(r"PR #(\d+):", prs_text)
    print(f"\nFound PR numbers: {pr_numbers}\n")

    for pr_num in pr_numbers:
        pr_number = int(pr_num)

        details = await get_pr_details_tool.handler({"repo": repo, "pr_number": pr_number})
        print(f"=== PR #{pr_number} DETAILS ===")
        print(details["content"][0]["text"])

        diff = await get_pr_diff_tool.handler({"repo": repo, "pr_number": pr_number})
        print(f"=== PR #{pr_number} DIFF ===")
        print(diff["content"][0]["text"])
        print()


asyncio.run(test_fetch("microsoft/vscode"))