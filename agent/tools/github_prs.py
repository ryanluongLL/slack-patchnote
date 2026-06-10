import os
import aiohttp
import re
from claude_agent_sdk import tool

GITHUB_API = "https://api.github.com"

@tool(
    name="get_recent_prs",
    description="Fetch recently merged pull requests from a GitHub repository.",
    input_schema={
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Repository in owner/name format, e.g. 'torvalds/linux'",
            },
            "limit": {
                "type": "integer",
                "description": "Number of PRs to return (max 10)",
                "default": 5,
            },
        },
        "required": ["repo"],
    },
)

async def get_recent_prs_tool(args):
    repo = args["repo"]
    limit = min(args.get("limit", 5), 10)
    token = os.environ.get("GITHUB_TOKEN", "")

    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    params={
        "state": "closed",
        "sort": "updated",
        "direction": "desc",
        "per_page": limit,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{GITHUB_API}/repos/{repo}/pulls",
            headers=headers,
            params=params,
        ) as resp:
            if resp.status != 200:
                return {
                    "content": [
                        {"type": "text", "text": f"GitHub API error: {resp.status}"}
                    ]
                }
            pulls = await resp.json()

    merged = [pr for pr in pulls if pr.get("merged_at")]

    if not merged:
        return{
            "content": [{"type": "text", "text": f"No merged PRs found in {repo} "}]
        }
    results = []
    for pr in merged:
        results.append(
            f"PR #{pr['number']}: {pr['title']}\n"
            f"Merged: {pr['merged_at']}\n"
            f"Body: {pr['body'] or '(no description)'}\n"
            f"URL: {pr['html_url']}"
        )

    return {"content": [{"type": "text", "text": "\n\n".join(results)}]}

@tool(
    name="get_pr_diff",
    description="Fetch the changed files and diffs for a specific merged PR.",
    input_schema={
        "type": "object",
        "properties":{
            "repo":{
                "type": "string",
                "description": "Repository in owner/name format, e.g. 'ryanluongLL/medvoice' ",
            },
            "pr_number":{
                "type": "integer",
                "description": "The pull request number",
            },
        },
        "required": ["repo", "pr_number"],
    }
)

async def get_pr_diff_tool(args):
    repo = args["repo"]
    pr_number = args["pr_number"]
    token = os.environ.get("GITHUB_TOKEN", "")

    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/files",
            headers=headers,
        ) as resp:
            if resp.status != 200:
                return{
                    "content":[
                        {"type": "text", "text": f"GitHub API error: {resp.status}"}
                    ]
                }
            files = await resp.json()

    #filter out noise: lock files, generated files, etc.
    skip_patterns = ["package-lock.json", "yarn.lock", "poetry.lock", ".min.js", ".min.css"]
    files = [f for f in files if not any(p in f["filename"] for p in skip_patterns)]

    if not files:
        return {"content": [{"type": "text", "text": "No meaningful file changes found."}]}
    
    results = []
    for f in files:
        patch = f.get("patch", "(binary or too large to display)")
        # truncate large patches so we don't blow the context window
        if len(patch) > 1500:
            patch = patch[:1500] + "\n... (truncated)"
        results.append(
            f"File: {f['filename']} (+{f['additions']} -{f['deletions']})\n{patch}"
        )
    return {"content": [{"type": "text", "text": "\n\n".join(results)}]}

@tool(
    name="get_pr_details",
    description="Fetch the full details of a PR including labels, linked issues, and description.",
    input_schema={
        "type": "object",
        "properties":{
            "repo":{
                "type":"string",
                "description": "Repository in owner/name format",
            },
            "pr_number":{
                "type": "integer",
                "description": "The pull request number",
            }
        },
        "required": ["repo", "pr_number"],
    },
)

async def get_pr_details_tool(args):
    repo = args["repo"]
    pr_number = args["pr_number"]
    token = os.environ.get("GITHUB_TOKEN", "")

    headers={"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}",
            headers=headers,
        ) as resp:
            if resp.status != 200:
                return{
                    "content": [
                        {"type": "text", "text": f"GitHub API error: {resp.status}" }
                    ]
                }
            pr = await resp.json()

    labels = [label["name"] for label in pr.get("labels", [])]
    body = pr.get("body") or "(no description)"

    # Parse linked issues from body (e.g. "Fixes #42", "Closes #7")
    linked = re.findall(r"(?:fixes|closes|resolves)\s+#(\d+)", body, re.IGNORECASE)

    result = (
        f"PR #{pr_number}: {pr['title']}\n"
        f"Labels: {', '.join(labels) or 'none'}\n"
        f"Linked issues: {', '.join(['#' + n for n in linked]) or 'none'}\n"
        f"Description:\n{body}"
    )
    
    return {"content": [{"type": "text", "text": result}]}