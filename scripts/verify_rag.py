# scripts/verify_rag.py
import asyncio
import sys
import uuid

from loguru import logger

from rag.builder import build_few_shot_context


async def run_verification() -> None:
    # Ensure logs are printed as JSON for the test
    logger.configure(
        handlers=[{"sink": sys.stdout, "format": "{message}", "serialize": True}]
    )

    # Mock parameters
    tenant_id = "00000000-0000-0000-0000-000000000001"
    trace_id = str(uuid.uuid4())
    news_text = (
        "AI agents are transforming software engineering by automating redundant tasks."
    )

    print("--- Starting RAG Builder Verification ---\n")

    context = await build_few_shot_context(
        news_text=news_text, tenant_id=tenant_id, trace_id=trace_id
    )

    print("\n--- Resulting Context Object ---")
    print(f"Examples Found: {len(context.examples)}")
    print(f"Similarity Scores: {context.similarity_scores}")
    print(f"Brand Voice: {context.brand_voice_summary}")


if __name__ == "__main__":
    asyncio.run(run_verification())
