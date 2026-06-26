# check_note_status.py
import asyncio
from dotenv import load_dotenv
load_dotenv()

from db.database import AsyncSessionLocal
from sqlalchemy import select
from db.models import ReleaseNote

async def check():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ReleaseNote).order_by(ReleaseNote.created_at.desc()).limit(5)
        )
        notes = result.scalars().all()
        for note in notes:
            print(f"{note.audience.value}: {note.status.value} (id: {note.id})")

asyncio.run(check())