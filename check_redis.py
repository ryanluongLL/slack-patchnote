# check_redis.py
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from upstash_redis.asyncio import Redis

async def check():
    redis = Redis(
        url=os.environ.get("UPSTASH_REDIS_REST_URL"),
        token=os.environ.get("UPSTASH_REDIS_REST_TOKEN"),
    )

    batch_keys = await redis.keys("patchnote:batch:*")
    window_keys = await redis.keys("patchnote:window:*")
    seen_keys = await redis.keys("patchnote:seen:*")

    print(f"Batch keys: {batch_keys}")
    print(f"Window keys: {window_keys}")
    print(f"Seen keys (sample): {seen_keys[:5]}")

    for key in batch_keys:
        items = await redis.lrange(key, 0, -1)
        print(f"\n{key}:")
        for item in items:
            print(f"  {item}")

asyncio.run(check())