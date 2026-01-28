"""Runtime patch to improve WebSurfer click handling for multi-line targets."""

from __future__ import annotations

import asyncio
from typing import Dict, Tuple

from autogen_ext.agents.web_surfer.playwright_controller import PlaywrightController
from playwright._impl._errors import TimeoutError
from playwright.async_api import Locator, Page


async def _agdbg_click_point(target: Locator) -> Tuple[float, float]:
    """Return a click coordinate guaranteed to lie within the element."""
    rects: list[Dict[str, float]] = await target.evaluate(
        "el => Array.from(el.getClientRects()).map(r => ({x: r.x, y: r.y, width: r.width, height: r.height}))"
    )
    for rect in rects:
        width = float(rect.get("width", 0.0))
        height = float(rect.get("height", 0.0))
        if width > 0 and height > 0:
            return float(rect.get("x", 0.0)) + width / 2, float(rect.get("y", 0.0)) + height / 2
    box = await target.bounding_box()
    if box is None:
        raise ValueError("Unable to determine bounding box for element.")
    return float(box["x"]) + float(box["width"]) / 2, float(box["y"]) + float(box["height"]) / 2


async def _agdbg_click_id(self: PlaywrightController, page: Page, identifier: str) -> Page | None:
    """Patched variant of PlaywrightController.click_id."""
    new_page: Page | None = None
    assert page is not None
    target = page.locator(f"[__elementId='{identifier}']")
    try:
        await target.wait_for(timeout=5000)
    except TimeoutError:
        raise ValueError("No such element.") from None

    await target.scroll_into_view_if_needed()
    await asyncio.sleep(0.3)

    click_x, click_y = await _agdbg_click_point(target)

    if self.animate_actions:
        await self.add_cursor_box(page, identifier)
        start_x, start_y = self.last_cursor_position
        await self.gradual_cursor_animation(page, start_x, start_y, click_x, click_y)
        await asyncio.sleep(0.1)
        try:
            async with page.expect_event("popup", timeout=1000) as page_info:  # type: ignore[arg-type]
                await page.mouse.click(click_x, click_y, delay=10)
                new_page = await page_info.value  # type: ignore[assignment]
                assert isinstance(new_page, Page)
                await self.on_new_page(new_page)
        except TimeoutError:
            pass
        await self.remove_cursor_box(page, identifier)
    else:
        try:
            async with page.expect_event("popup", timeout=1000) as page_info:  # type: ignore[arg-type]
                await page.mouse.click(click_x, click_y, delay=10)
                new_page = await page_info.value  # type: ignore[assignment]
                assert isinstance(new_page, Page)
                await self.on_new_page(new_page)
        except TimeoutError:
            pass
    return new_page


if not getattr(PlaywrightController, "_agdbg_click_patch", False):
    PlaywrightController._agdbg_original_click_id = PlaywrightController.click_id  # type: ignore[attr-defined]
    PlaywrightController.click_id = _agdbg_click_id  # type: ignore[assignment]
    PlaywrightController._agdbg_click_patch = True  # type: ignore[attr-defined]
