from __future__ import annotations

from src.tools.registry import tool


@tool(
    name="scrape_page",
    description="Scrape a web page and return its visible text content using Playwright headless browser.",
    parameters={
        "url": {"type": "string", "description": "The URL of the web page to scrape"},
        "max_chars": {"type": "integer", "description": "Maximum characters to return (default 10000)"},
    },
)
async def scrape_page(url: str, max_chars: int = 10000) -> str:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return "Error: playwright not installed. Run: pip install playwright && playwright install chromium"

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            content = await page.evaluate("""() => {
                for (const el of document.querySelectorAll('script, style, nav, footer, header, aside')) {
                    el.remove();
                }
                return document.body ? document.body.innerText : '';
            }""")
            await browser.close()
    except Exception as exc:
        return f"Error scraping {url}: {exc}"

    text = content.strip()
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n... (truncated, total {len(content)} chars)"
    return text if text else f"(empty page: {url})"
