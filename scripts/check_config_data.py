import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.config_service import ConfigService

async def check_data():
    try:
        configs = await ConfigService.get_all_from_db()
        print(f"Found {len(configs)} configs:")
        for key, config in configs.items():
            val = config.get("value")
            val_preview = val[:5] + "..." + val[-5:] if val and len(val) > 10 else val
            print(f"Key: {key}, Value: {val_preview}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_data())
