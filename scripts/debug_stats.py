import asyncio
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import database
from app.core.orm import AsyncSessionLocal
from sqlalchemy import text

async def debug_stats():
    await database.init_db()

    async with AsyncSessionLocal() as session:
        # 1. 检查总数
        access_count = (await session.execute(text("SELECT COUNT(*) FROM ai_agent_access_logs"))).scalar_one()
        trace_count = (await session.execute(text("SELECT COUNT(*) FROM ai_agent_execution_traces"))).scalar_one()

        print(f"Total Access Logs: {access_count}")
        print(f"Total Execution Traces: {trace_count}")

        # 2. 检查今日数据 (UTC/Local 混合排查)
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_str = today_start.strftime('%Y-%m-%d %H:%M:%S')

        print(f"\nChecking data since {today_start_str}...")

        access_today = (
            await session.execute(
                text("SELECT COUNT(*) FROM ai_agent_access_logs WHERE created_at >= :today_start"),
                {"today_start": today_start},
            )
        ).scalar_one()
        trace_today = (
            await session.execute(
                text("SELECT COUNT(*) FROM ai_agent_execution_traces WHERE created_at >= :today_start"),
                {"today_start": today_start},
            )
        ).scalar_one()

        print(f"Access Logs today: {access_today}")
        print(f"Execution Traces today: {trace_today}")

        # 3. 如果有数据，看几条详情
        if trace_today > 0:
            rows = (
                await session.execute(
                    text(
                        "SELECT event_type, status, created_at "
                        "FROM ai_agent_execution_traces "
                        "ORDER BY created_at DESC LIMIT 5"
                    )
                )
            ).all()
            print("\nRecent Traces Detail:")
            for r in rows:
                print(f" - {r[0]} | {r[1]} | {r[2]}")

    await database.close_db()

if __name__ == "__main__":
    asyncio.run(debug_stats())
