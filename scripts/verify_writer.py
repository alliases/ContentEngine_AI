# scripts/verify_writer.py
import asyncio
import sys
from datetime import UTC, datetime

from dotenv import load_dotenv
from loguru import logger

from agents.state import FewShotContext, RawNewsItem
from agents.writer import WriterAgent

# Explicitly load .env to ensure OPENAI_API_KEY is available
load_dotenv()


async def run_verification() -> None:
    logger.configure(
        handlers=[{"sink": sys.stdout, "format": "{message}", "serialize": True}]
    )

    print("--- Starting Writer Agent Verification ---\n")

    # Mock context
    news = RawNewsItem(
        title="OpenAI announces new structured outputs feature",
        text="OpenAI has released a new API update that guarantees 100% adherence to JSON schemas supplied by developers, eliminating the need for complex prompt engineering for output formatting.",
        source="TechBlog",
        url="https://example.com/news",
        published_at=datetime.now(UTC),
        relevance_score=0.95,
    )

    context = FewShotContext(
        examples=[
            "Struggling with bad JSON from LLMs?\n\nNot anymore. OpenAI just dropped a bomb. \n\n<keyword>Structured Outputs</keyword> are here.",
        ],
        similarity_scores=[0.88],
        brand_voice_summary="Punchy, direct, heavily tech-focused. Uses short sentences.",
    )

    agent = WriterAgent()

    try:
        slides = await agent.generate(topic=news.title, news=news, context=context)

        print("\n--- Generation Success ---")
        for slide in slides:
            print(f"Slide {slide.position}:")
            print(f"  Title: {slide.title}")
            print(f"  Body:  {slide.body_text}")
            print(f"  Keywords: {slide.keywords}")
            print(f"  Chars: {slide.char_count}\n")

    except Exception as e:
        print(f"\n[ERROR] Generation failed: {e}")


if __name__ == "__main__":
    asyncio.run(run_verification())
