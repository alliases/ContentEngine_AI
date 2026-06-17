# renderer/engine.py
from pathlib import Path

from anyio import Path as AsyncPath
from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger
from playwright.async_api import async_playwright
from pydantic import BaseModel

from agents.state import SlideContent


class RenderResult(BaseModel):
    png_paths: list[str]
    pdf_path: str


# Initialize Jinja2 environment securely
TEMPLATE_DIR = Path(__file__).parent / "templates"
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


def _process_keywords(text: str) -> str:
    """Replaces <keyword> tags with styled HTML spans."""
    return text.replace("<keyword>", "<span class='keyword'>").replace(
        "</keyword>", "</span>"
    )


async def render_carousel(
    slides: list[SlideContent], tenant_id: str, carousel_id: str
) -> RenderResult:
    """
    Renders slides to 1080x1080 PNGs and a combined PDF using Playwright.
    Enforces strict tenant isolation via path boundaries.
    """
    # Anti-Spaghetti: Strict Tenant Isolation (Invariant 1)
    output_dir = AsyncPath(f"storage/{tenant_id}/{carousel_id}")
    await output_dir.mkdir(parents=True, exist_ok=True)

    slide_template = env.get_template("slide.html.j2")
    carousel_template = env.get_template("carousel.html.j2")

    png_paths: list[str] = []
    pdf_path = str(output_dir / "carousel.pdf")

    logger.info(
        {
            "event": "render_start",
            "carousel_id": carousel_id,
            "tenant_id": tenant_id,
            "slides_count": len(slides),
        }
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Generate separate PNGs (Instagram 1080x1080)
        await page.set_viewport_size({"width": 1080, "height": 1080})
        for slide in slides:
            html_content = slide_template.render(
                slide=slide, body_html=_process_keywords(slide.body_text)
            )
            await page.set_content(html_content, wait_until="networkidle")

            # Anti-Spaghetti: Wait for Fitty.js and Fonts (Invariant 3)
            await page.wait_for_function("window.__RENDER_COMPLETE__ === true")

            png_path = str(output_dir / f"slide_{slide.position}.png")
            await page.screenshot(path=png_path, full_page=False)
            png_paths.append(png_path)

        # Generate combined PDF (LinkedIn)
        slides_data = [
            {"slide": s, "body_html": _process_keywords(s.body_text)} for s in slides
        ]
        full_html = carousel_template.render(slides_data=slides_data)
        await page.set_content(full_html, wait_until="networkidle")
        await page.wait_for_function("window.__RENDER_COMPLETE__ === true")

        await page.pdf(
            path=pdf_path,
            print_background=True,
            width="10.8in",  # 1080px equivalent at 100dpi
            height="10.8in",
        )

        await browser.close()

    logger.info(
        {
            "event": "render_complete",
            "carousel_id": carousel_id,
            "pdf_path": pdf_path,
        }
    )
    return RenderResult(png_paths=png_paths, pdf_path=pdf_path)
