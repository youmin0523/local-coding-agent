"""Browser automation tools (Playwright): screenshot + E2E smoke check.

Lets the agent open a real browser to test web apps — capture screenshots and
assert that pages render expected content (E2E). `RiskLevel.NETWORK` (gated).
Playwright is an optional extra; if it isn't installed the tools return a clear
install hint instead of failing hard:  `uv sync --extra browser && uv run
playwright install chromium`.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from typing import Any

from lca.core.errors import ToolError
from lca.tools.base import Artifact, RiskLevel, ToolContext, ToolResult, ToolSpec

_INSTALL_HINT = (
    "browser support requires: uv sync --extra browser && uv run playwright install chromium"
)
_SHOT_DIR = ".lca/screenshots"


def _check_url(url: str) -> str:
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        raise ToolError("url must start with http:// or https://")
    return url


@contextlib.asynccontextmanager
async def _page(url: str, *, headless: bool = True, timeout_ms: int = 20_000) -> AsyncIterator[Any]:
    from playwright.async_api import async_playwright  # lazy: optional `browser` extra

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        try:
            page = await browser.new_page()
            await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            yield page
        finally:
            await browser.close()


class BrowserScreenshotTool:
    spec = ToolSpec(
        name="browser_screenshot",
        description=(
            "Open a URL in a headless browser and save a screenshot (full page or a CSS "
            "selector) into the workspace. Use it to see how a web app renders."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "http(s) URL (e.g. a local dev server)."},
                "selector": {"type": "string", "description": "Optional CSS selector to capture."},
                "full_page": {
                    "type": "boolean",
                    "description": "Capture the full scrollable page.",
                },
                "filename": {"type": "string", "description": "Output .png name."},
            },
            "required": ["url"],
        },
        risk=RiskLevel.NETWORK,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        url = _check_url(str(args["url"]))
        selector = args.get("selector")
        full_page = bool(args.get("full_page", False))
        name = str(args.get("filename") or "screenshot.png")
        if not name.endswith(".png"):
            name += ".png"
        out_dir = ctx.workspace_root / _SHOT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / name
        try:
            async with _page(url) as page:
                if selector:
                    await page.locator(str(selector)).screenshot(path=str(dest))
                else:
                    await page.screenshot(path=str(dest), full_page=full_page)
                title = await page.title()
        except ImportError:
            return ToolResult.error(_INSTALL_HINT)
        except Exception as exc:
            return ToolResult.error(f"screenshot failed for {url}: {exc}")
        rel = f"{_SHOT_DIR}/{name}"
        return ToolResult.ok_text(
            f"saved screenshot of '{title}' to {rel}",
            artifacts=[Artifact(kind="file", title=name, uri=rel)],
        )


class BrowserCheckTool:
    spec = ToolSpec(
        name="browser_check",
        description=(
            "Open a URL in a headless browser and verify it renders expected content — wait "
            "for a CSS selector and/or assert text is present. An E2E smoke check."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "http(s) URL to check."},
                "selector": {"type": "string", "description": "CSS selector that must appear."},
                "expect_text": {"type": "string", "description": "Text that must be present."},
            },
            "required": ["url"],
        },
        risk=RiskLevel.NETWORK,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        url = _check_url(str(args["url"]))
        selector = args.get("selector")
        expect_text = args.get("expect_text")
        try:
            async with _page(url) as page:
                title = await page.title()
                if selector:
                    await page.wait_for_selector(str(selector), timeout=15_000)
                body = await page.content()
        except ImportError:
            return ToolResult.error(_INSTALL_HINT)
        except Exception as exc:
            return ToolResult(ok=False, content=f"E2E check FAILED for {url}: {exc}", is_truth=True)

        if expect_text and str(expect_text) not in body:
            return ToolResult(
                ok=False,
                content=f"E2E check FAILED: '{expect_text}' not found on {url} (title: {title}).",
                is_truth=True,
            )
        detail = f"selector '{selector}' present; " if selector else ""
        detail += f"text '{expect_text}' present; " if expect_text else ""
        return ToolResult(
            ok=True,
            content=f"E2E check PASSED for {url} (title: {title}). {detail}".strip(),
            is_truth=True,
        )
