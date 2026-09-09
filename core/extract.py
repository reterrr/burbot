import httpx
from pydantic import AnyHttpUrl, TypeAdapter

import asyncio
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import (
    BrowserContext,
    Page,
    async_playwright, ViewportSize,
)

url_adapter = TypeAdapter(AnyHttpUrl)


async def validate_url(
        client: httpx.AsyncClient,
        url: str,
) -> AnyHttpUrl | None:
    try:
        validated_url = url_adapter.validate_python(url)

        response = await client.get(
            str(validated_url),
            follow_redirects=True,
        )

        if response.status_code >= 400:
            return None

        return validated_url

    except (ValueError, httpx.HTTPError):
        return None


async def valid_urls(urls: list[str]) -> list[AnyHttpUrl]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        results = await asyncio.gather(
            *(validate_url(client, url) for url in urls)
        )

    return [url for url in results if url is not None]


urls = [
    "https://rarr.rzeszow.pl/projekty/generator-kompetencji-30/",
    "https://bony.fundacjainicjatyw.eu/",
    "https://frrr.pl/projekty/tbr.html",
]


async def validate_page(page: Page) -> None:
    title = await page.title()
    body_text = await page.locator("body").inner_text()

    suspicious_phrases = {
        "access denied",
        "checking your browser",
        "verify you are human",
        "captcha",
        "403 forbidden",
    }

    normalized_text = body_text.lower()

    for phrase in suspicious_phrases:
        if phrase in normalized_text:
            raise RuntimeError(
                f"Suspicious page detected: {phrase!r}"
            )

    if len(body_text.strip()) < 100:
        raise RuntimeError(
            f"Page appears empty; title={title!r}"
        )


async def scroll_to_bottom(page: Page) -> None:
    previous_height = 0

    for _ in range(20):
        current_height = await page.evaluate(
            "document.body.scrollHeight"
        )

        if current_height == previous_height:
            break

        previous_height = current_height

        await page.evaluate(
            "window.scrollTo(0, document.body.scrollHeight)"
        )

        await page.wait_for_timeout(500)


def page_slug(url: str) -> str:
    parsed = urlparse(url)

    domain = parsed.netloc.replace(":", "-")
    path = parsed.path.strip("/").replace("/", "-")

    return f"{domain}-{path or 'index'}"


def screenshot_path(url: str) -> Path:
    return Path("screenshots") / f"{page_slug(url)}.png"


async def process_page(
        context: BrowserContext,
        url: str,
) -> str:
    page = await context.new_page()

    console_errors: list[str] = []
    failed_requests: list[str] = []

    response = None

    page.on(
        "console",
        lambda message: (
            console_errors.append(message.text)
            if message.type == "error"
            else None
        ),
    )

    page.on(
        "requestfailed",
        lambda request: failed_requests.append(request.url),
    )

    try:
        response = await page.goto(
            url=url,
            wait_until="domcontentloaded",
            timeout=30_000,
        )

        await page.locator("body").wait_for(
            state="visible",
            timeout=15_000,
        )

        await scroll_to_bottom(page)
        await validate_page(page)

        html = await page.content()

        output_path = screenshot_path(url)
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        await page.screenshot(
            path=output_path,
            full_page=True,
        )

        print("========")
        print(f"Requested URL: {url}")
        print(f"Final URL: {page.url}")
        print(
            f"Status: {response.status if response else None}"
        )
        print(f"Title: {await page.title()}")
        print(f"HTML length: {len(html)}")
        print(f"Screenshot: {output_path}")

        return html

    except Exception as error:
        debug_directory = Path("debug") / page_slug(url)
        debug_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            await page.screenshot(
                path=debug_directory / "page.png",
                full_page=True,
            )
        except Exception as screenshot_error:
            console_errors.append(
                f"Screenshot failed: {screenshot_error}"
            )

        try:
            html = await page.content()
        except Exception:
            html = ""

        (debug_directory / "page.html").write_text(
            html,
            encoding="utf-8",
        )

        details = [
            f"Requested URL: {url}",
            f"Final URL: {page.url}",
            (
                "Status: "
                f"{response.status if response else None}"
            ),
            f"Error: {type(error).__name__}: {error}",
            "",
            "Console errors:",
            *(console_errors or ["None"]),
            "",
            "Failed requests:",
            *(failed_requests or ["None"]),
        ]

        (debug_directory / "details.txt").write_text(
            "\n".join(details),
            encoding="utf-8",
        )

        raise RuntimeError(
            f"Failed to process {url}. "
            f"Debug files saved in {debug_directory}"
        ) from error

    finally:
        await page.close()


async def main() -> None:
    validated_urls = await valid_urls(urls)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            channel="chromium",
        )

        context = await browser.new_context(
            viewport=ViewportSize(width=1920, height=1080),
            locale="pl-PL",
            timezone_id="Europe/Warsaw",
            color_scheme="light",
        )

        try:
            for validated_url in validated_urls:
                url = str(validated_url)

                try:
                    html = await process_page(
                        context=context,
                        url=url,
                    )


                    # Тут далі передаєш HTML в аналізатор:
                    # await analyze_html(url=url, html=html)

                except RuntimeError as error:
                    print(error)

        finally:
            await context.close()
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
