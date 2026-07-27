import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core import database
from app.core.orm import AsyncSessionLocal
from app.models.user import User
# Register the association table before SQLAlchemy configures User.roles.
from app.models.permission import UserRoleRelation  # noqa: F401
from app.services.auth_service import AuthService

async def create_admin_key(username: str = "admin"):
    await database.init_db()
    try:
        async with AsyncSessionLocal() as session:
            user = (
                await session.execute(select(User).where(User.user_name == username))
            ).scalar_one_or_none()

            if user:
                if user.role != "admin":
                    raise RuntimeError(
                        f"User '{username}' exists but is not an admin; refusing to elevate it."
                    )
                print(f"Resetting ADMIN key for existing user: {username}")
                api_key = await AuthService.reset_api_key(user.id, db=session)
                action = "reset"
            else:
                print(f"Generating ADMIN key for new user: {username}")
                api_key = await AuthService.generate_api_key(
                    username,
                    role="admin",
                    remark="Created by admin bootstrap script",
                    db=session,
                )
                action = "created"
        
        print(f"\n{'='*60}")
        print(f"SUCCESS! Admin API Key {action}")
        print(f"{'='*60}")
        print(f"Username: {username}")
        print(f"API Key:  {api_key}")
        print(f"Role:     admin")
        print(f"{'='*60}")
        print("\n⚠️  Please save this key securely - it won't be shown again!")
        print("\nYou can use this key to login to the admin portal:")
        print(f"  Username: {username}")
        print(f"  API Key:  {api_key}")
        
    finally:
        await database.close_db()

if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else "admin"
    asyncio.run(create_admin_key(username))
