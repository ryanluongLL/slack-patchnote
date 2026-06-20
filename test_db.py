# test_db.py
import asyncio
from dotenv import load_dotenv
load_dotenv()
from db.database import init_db

async def test():
    await init_db()
    print("Tables created successfully")

asyncio.run(test())