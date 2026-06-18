# tests/unit/test_renderer.py
from typing import Any, cast

import pytest
from playwright.async_api import async_playwright

from agents.state import SlideContent
from renderer.engine import _process_keywords, env


async def get_rendered_metrics(text: str) -> dict[str, float]:
    """
    Renders a test slide and returns computed font size and layout heights.
    Executes in an isolated Playwright context to prevent zombie processes.
    """
    slide = SlideContent(
        position=1,
        title="Scaling Test",
        body_text=text,
        keywords=["test"],
        char_count=len(text),
    )

    template = env.get_template("slide.html.j2")
    html_content = template.render(
        slide=slide, body_html=_process_keywords(slide.body_text)
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Instagram resolution
        await page.set_viewport_size({"width": 1080, "height": 1080})
        await page.set_content(html_content, wait_until="networkidle")

        # Anti-Spaghetti: Enforce rendering sync invariant
        await page.wait_for_function("window.__RENDER_COMPLETE__ === true")

        # CRITICAL: Fitty applies styles asynchronously via requestAnimationFrame.
        # We must yield the event loop to let the browser physically render the new font size.
        await page.wait_for_timeout(250)

        raw_metrics = cast(
            dict[str, Any],
            await page.evaluate("""() => {
            const fitText = document.querySelector('.fit-text');
            const slide = document.querySelector('.slide');
            return {
                fontSize: parseFloat(window.getComputedStyle(fitText).fontSize),
                scrollHeight: slide.scrollHeight,
                clientHeight: slide.clientHeight
            };
        }"""),
        )

        await browser.close()

        return {
            "fontSize": float(raw_metrics["fontSize"]),
            "scrollHeight": float(raw_metrics["scrollHeight"]),
            "clientHeight": float(raw_metrics["clientHeight"]),
        }


@pytest.mark.asyncio
async def test_font_scaling_relative() -> None:
    """
    Verifies that fitty.js dynamically scales the font down
    as the text length increases.
    """
    short_text = "Short text."
    medium_text = "This is a medium length text that takes up more space."
    long_text = "Here is a significantly longer text block. " * 10

    short_metrics = await get_rendered_metrics(short_text)
    medium_metrics = await get_rendered_metrics(medium_text)
    long_metrics = await get_rendered_metrics(long_text)

    # Invariant: More text -> Smaller font
    assert short_metrics["fontSize"] > medium_metrics["fontSize"]
    assert medium_metrics["fontSize"] > long_metrics["fontSize"]
    assert long_metrics["fontSize"] >= 24.0  # defined minSize in base template


@pytest.mark.asyncio
async def test_text_does_not_overflow() -> None:
    """
    Ensures that even with excessively long text, the content
    does not break out of the slide container boundaries.
    """
    extremely_long_text = "Overflow constraint testing. " * 50
    metrics = await get_rendered_metrics(extremely_long_text)

    # Invariant: Content height must be bounded by container height
    assert metrics["scrollHeight"] <= metrics["clientHeight"]
