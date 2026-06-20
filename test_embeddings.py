import asyncio
from dotenv import load_dotenv
load_dotenv()

from agent.embeddings import build_pr_summary_text, embed_pr_summary
from db.database import AsyncSessionLocal, init_db
from db.crud import create_release, create_pr_embedding
from db.models import AudienceType


async def test():
    await init_db()

    summary = build_pr_summary_text(
        pr_number=999,
        pr_title="Fix scrollbar alignment in chat view",
        details_text="Labels: bug, ui. Linked issues: #888",
        diff_text="sessionView.ts: moved .session-view-content out of centered band",
    )

    print(f"Summary text:\n{summary}\n")

    embedding = await embed_pr_summary(summary)
    print(f"Embedding length: {len(embedding)}")
    print(f"First 5 values: {embedding[:5]}")

    async with AsyncSessionLocal() as session:
        release = await create_release(
            session=session,
            repo="test/repo",
            pr_numbers=[999],
            pr_titles=["Fix scrollbar alignment"],
            raw_data="test data",
            triggered_by="test",
        )

        pr_embedding = await create_pr_embedding(
            session=session,
            release_id=release.id,
            repo="test/repo",
            pr_number=999,
            pr_title="Fix scrollbar alignment in chat view",
            summary_text=summary,
            embedding=embedding,
        )
        print(f"\nStored embedding with id: {pr_embedding.id}")


asyncio.run(test())