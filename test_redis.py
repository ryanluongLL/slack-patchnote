# test_redis.py
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from upstash_redis.asyncio import Redis

async def test():
    redis = Redis(
        url=os.environ.get("UPSTASH_REDIS_REST_URL"),
        token=os.environ.get("UPSTASH_REDIS_REST_TOKEN"),
    )

    await redis.set("patchnote:test", "connected")
    value = await redis.get("patchnote:test")
    print(f"Redis connection: {value}")
    await redis.delete("patchnote:test")

asyncio.run(test())