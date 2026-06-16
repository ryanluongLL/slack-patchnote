# test_db.py
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test():
    engine = create_async_engine(
        os.environ.get("DATABASE_URL"),
        connect_args={"ssl": "require"},
    )
    
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM releases"))
        count = result.fetchone()[0]
        print(f"Releases in database: {count}")
        
        result = await conn.execute(text("SELECT COUNT(*) FROM release_notes"))
        count = result.fetchone()[0]
        print(f"Release notes in database: {count}")
    
    await engine.dispose()

asyncio.run(test())