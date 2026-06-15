# scripts/seed_db.py

import asyncio
import uuid

from sqlalchemy import select

from api.security import get_password_hash
from db.models import Tenant, User
from db.session import async_session_maker


async def seed_data() -> None:
    print("Starting database seeding...")
    async with async_session_maker() as session:
        # 1. Check or create default tenant
        tenant_stmt = select(Tenant).where(Tenant.name == "Test Enterprise Tenant")
        tenant_result = await session.execute(tenant_stmt)
        tenant = tenant_result.scalar_one_or_none()

        if not tenant:
            tenant = Tenant(
                id=uuid.uuid4(),
                name="Test Enterprise Tenant",
                qdrant_collection="posts_test_enterprise",
            )
            session.add(tenant)
            await session.flush()
            print(f"Created Tenant with ID: {tenant.id}")
        else:
            print(f"Tenant already exists with ID: {tenant.id}")

        # 2. Check or create default admin user
        user_stmt = select(User).where(User.email == "admin@contentengine.ai")
        user_result = await session.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if not user:
            # Using Argon2 hasher from security module
            hashed_password = get_password_hash("SuperSecretPassword123")
            user = User(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                email="admin@contentengine.ai",
                hashed_password=hashed_password,
            )
            session.add(user)
            print(f"Created User: {user.email}")
        else:
            print(f"User {user.email} already exists.")

        await session.commit()
    print("Seeding completed successfully.")


if __name__ == "__main__":
    asyncio.run(seed_data())
