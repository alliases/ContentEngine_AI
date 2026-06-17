# scripts/verify_renderer.py
import asyncio

from anyio import Path as AsyncPath

from agents.state import SlideContent
from renderer.engine import render_carousel


async def main() -> None:
    tenant_id = "test_tenant"
    carousel_id = "test_carousel_001"

    slides = [
        SlideContent(
            position=1,
            title="AI Architecture",
            body_text="In this carousel, we will explore the <keyword>LangGraph</keyword> multi-agent pipeline.",
            keywords=["LangGraph"],
            char_count=90,
        ),
        SlideContent(
            position=2,
            title=None,
            body_text="A robust system requires strict <keyword>tenant isolation</keyword> and fault tolerance mechanisms.",
            keywords=["tenant isolation"],
            char_count=85,
        ),
    ]

    print("🚀 Starting isolated rendering test...")
    result = await render_carousel(slides, tenant_id, carousel_id)

    for png in result.png_paths:
        if await AsyncPath(png).exists():
            print(f"✅ Created PNG: {png}")
        else:
            print(f"❌ Failed to create PNG: {png}")

    if await AsyncPath(result.pdf_path).exists():
        print(f"✅ Created PDF: {result.pdf_path}")
    else:
        print(f"❌ Failed to create PDF: {result.pdf_path}")


if __name__ == "__main__":
    asyncio.run(main())
