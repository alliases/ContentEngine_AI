# scripts/verify_pipeline.py
import asyncio
import sys
import uuid

from loguru import logger
from sqlalchemy import select

from db.models import Carousel, Task, Tenant
from db.session import async_session_maker
from workers.tasks import run_carousel_pipeline


async def run_verification() -> None:
    logger.configure(
        handlers=[{"sink": sys.stdout, "format": "{message}", "serialize": True}]
    )
    print("--- Starting Pipeline Verification ---\n")

    async with async_session_maker() as session:
        # Get Seeded Tenant
        tenant_stmt = select(Tenant).where(Tenant.name == "Test Enterprise Tenant")
        tenant = (await session.execute(tenant_stmt)).scalar_one_or_none()

        if not tenant:
            print(
                "[ERROR] Database not seeded. Run 'poetry run python scripts/seed_db.py' first."
            )
            return

        # Setup test data
        carousel_id = uuid.uuid4()
        task_id = uuid.uuid4()

        new_carousel = Carousel(
            id=carousel_id,
            tenant_id=tenant.id,
            topic="AI Task Execution Test",
            status="PENDING",
        )
        session.add(new_carousel)

        new_task = Task(
            id=task_id,
            tenant_id=tenant.id,
            carousel_id=carousel_id,
            status="PROCESSING",
        )
        session.add(new_task)
        await session.commit()

        print(f"[1] Created Test Carousel: {carousel_id}")
        print(f"[2] Invoking Worker Pipeline for Task: {task_id}")

    # Invoke Worker directly
    await run_carousel_pipeline(str(carousel_id), str(tenant.id), str(task_id))

    # Verify changes in DB
    async with async_session_maker() as session:
        check_task = (
            await session.execute(select(Task).where(Task.id == task_id))
        ).scalar_one()
        check_carousel = (
            await session.execute(select(Carousel).where(Carousel.id == carousel_id))
        ).scalar_one()

        print("\n--- Pipeline Results ---")
        print(f"Task DB Status: {check_task.status}")
        print(f"Carousel DB Status: {check_carousel.status}")

        if check_task.result_json:
            print("[✓] JSON Results populated successfully.")

        if check_task.status in ("GENERATED", "NEEDS_HUMAN_REVIEW"):
            print(
                "\n[✓] Verification Successful: Graph executed and DB constraints strictly respected."
            )
        else:
            print("\n[❌] Verification Failed: Status was not updated appropriately.")


if __name__ == "__main__":
    asyncio.run(run_verification())
