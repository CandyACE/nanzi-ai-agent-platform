import asyncio
import sys
import os
import httpx

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.config_service import ConfigService

async def main():
    print("Fetching Config...")
    configs = await ConfigService.get_all_from_db()
    base_url = (configs.get("ragflow_api_url") or {}).get("value")
    api_key = (configs.get("ragflow_api_key") or {}).get("value")

    if not base_url or not api_key:
        print("Error: RAGFlow config not found in DB.")
        return

    print(f"URL: {base_url}")
    url = f"{base_url.rstrip('/')}/api/v1/datasets"
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"page": 1, "page_size": 100}

    print(f"Requesting: {url}")
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params)
        print(f"Status: {resp.status_code}")
        print(f"Raw Response Body:\n{resp.text}")

if __name__ == "__main__":
    asyncio.run(main())
