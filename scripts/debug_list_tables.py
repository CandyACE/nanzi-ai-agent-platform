import asyncio
import os
import sys
from sqlalchemy import inspect

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.orm import engine

async def list_tables():
    try:
        async with engine.connect() as connection:
            tables = await connection.run_sync(lambda sync_connection: inspect(sync_connection).get_table_names())
        print("Current Tables:")
        for table in tables:
            print(f"- {table}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(list_tables())
