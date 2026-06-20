import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import Release, ReleaseNote, AudienceType, ApprovalStatus
from db.models import Release, ReleaseNote, AudienceType, ApprovalStatus, PREmbedding

async def create_release(
    session: AsyncSession,
    repo: str,
    pr_numbers: list[int],
    pr_titles: list[str],
    raw_data: str,
    triggered_by: str = "webhook",
) -> Release:
    """Create a new release record."""
    release = Release(
        repo=repo,
        pr_numbers=",".join(str(n) for n in pr_numbers),
        pr_titles=",".join(pr_titles),
        raw_data=raw_data,
        triggered_by=triggered_by,
    )
    session.add(release)
    await session.commit()
    await session.refresh(release)
    return release


async def create_release_note(
    session: AsyncSession,
    release_id: uuid.UUID,
    audience: AudienceType,
    content: str,
    slack_channel_id: str | None = None,
    slack_message_ts: str | None = None,
) -> ReleaseNote:
    """Create a release note for one audience."""
    note = ReleaseNote(
        release_id=release_id,
        audience=audience,
        content=content,
        status=ApprovalStatus.pending,
        slack_channel_id=slack_channel_id,
        slack_message_ts=slack_message_ts,
    )
    session.add(note)
    await session.commit()
    await session.refresh(note)
    return note


async def get_releases_for_repo(
    session: AsyncSession,
    repo: str,
    limit: int = 10,
) -> list[Release]:
    """Fetch recent releases for a repo."""
    result = await session.execute(
        select(Release)
        .where(Release.repo == repo)
        .order_by(Release.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_notes_for_release(
    session: AsyncSession,
    release_id: uuid.UUID,
) -> list[ReleaseNote]:
    """Fetch all notes for a release."""
    result = await session.execute(
        select(ReleaseNote).where(ReleaseNote.release_id == release_id)
    )
    return list(result.scalars().all())


async def update_note_status(
    session: AsyncSession,
    note_id: uuid.UUID,
    status: ApprovalStatus,
) -> ReleaseNote | None:
    """Update approval status for a note."""
    result = await session.execute(
        select(ReleaseNote).where(ReleaseNote.id == note_id)
    )
    note = result.scalar_one_or_none()
    if note:
        note.status = status
        await session.commit()
        await session.refresh(note)
    return note


async def create_pr_embedding(
    session: AsyncSession,
    release_id: uuid.UUID,
    repo: str,
    pr_number: int,
    pr_title: str,
    summary_text: str,
    embedding: list[float],
) -> PREmbedding:
    """Store a PR's embedding for later similarity search and clustering."""
    pr_embedding = PREmbedding(
        release_id=release_id,
        repo=repo,
        pr_number=pr_number,
        pr_title=pr_title,
        summary_text=summary_text,
        embedding=embedding,
    )
    session.add(pr_embedding)
    await session.commit()
    await session.refresh(pr_embedding)
    return pr_embedding

