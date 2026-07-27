import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import database
from app.services.auth_service import AuthService
# Register the association table before SQLAlchemy configures User.roles.
from app.models.permission import UserRoleRelation  # noqa: F401

async def create_key(username: str):
    await database.init_db()
    try:
        print(f"Generating key for user: {username}")
        api_key = await AuthService.generate_api_key(username)
        print(f"SUCCESS! API Key for '{username}':")
        print(f"\n{api_key}\n")
        print("Please save this key securely.")
    finally:
        await database.close_db()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python create_key.py <username>")
        sys.exit(1)
    asyncio.run(create_key(sys.argv[1]))
