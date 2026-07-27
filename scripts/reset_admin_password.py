"""Safely set or reset an administrator's local login password."""

import asyncio
import getpass
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


def validate_password(password: str, confirmation: str) -> str:
    if len(password) < 6:
        raise ValueError("密码至少 6 个字符")
    if password != confirmation:
        raise ValueError("两次输入的密码不一致")
    return password


def prompt_password() -> str:
    password = getpass.getpass("New admin password: ")
    confirmation = getpass.getpass("Confirm admin password: ")
    return validate_password(password, confirmation)


async def reset_admin_password(username: str = "admin", password: str | None = None) -> None:
    await database.init_db()
    try:
        password = password if password is not None else prompt_password()
        async with AsyncSessionLocal() as session:
            user = (
                await session.execute(select(User).where(User.user_name == username))
            ).scalar_one_or_none()
            if not user:
                raise RuntimeError(f"User '{username}' does not exist.")
            if user.role != "admin":
                raise RuntimeError(
                    f"User '{username}' exists but is not an admin; refusing to change its password."
                )

            if not await AuthService.set_user_password(user.id, password, db=session):
                raise RuntimeError(f"Failed to update password for user '{username}'.")

        print(f"✅ Admin password reset successfully for user: {username}")
    finally:
        await database.close_db()


if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else "admin"
    asyncio.run(reset_admin_password(username))
