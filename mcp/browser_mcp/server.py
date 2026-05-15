"""
browser-mcp: Playwright-backed tools for CCTV snapshots and marketplace search.

Tools exposed:
  - cctv_snapshot(camera_id)            -> {path, ts, camera_id}
  - marketplace_search(platform, query) -> [{url, title, price, image_url, posted_at, location}]
  - marketplace_get_listing(url)        -> {title, price, description, images: [paths], seller, location}

Image artifacts are written under SHARED_DIR/photos/<camera_or_listing>/<ts>.jpg
so worker agents can hand the path straight to vision-mcp.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright, Browser

SHARED_DIR = Path(os.environ.get("LACAKIN_SHARED", str(Path.home() / "lacakin" / "shared")))
PHOTOS_DIR = SHARED_DIR / "photos"
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

CAMERAS_PATH = Path(__file__).parent / "cameras.json"
CAMERAS = {c["id"]: c for c in json.loads(CAMERAS_PATH.read_text())}

mcp = FastMCP("browser-mcp")
_browser: Browser | None = None
_browser_lock = asyncio.Lock()


async def _get_browser() -> Browser:
    """Lazily start one shared Chromium across tool calls."""
    global _browser
    async with _browser_lock:
        if _browser is None:
            pw = await async_playwright().start()
            _browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
    return _browser


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


# ─────────────────────────────────────────────────────────────────────────
# CCTV
# ─────────────────────────────────────────────────────────────────────────
@mcp.tool()
async def cctv_snapshot(camera_id: str) -> dict[str, Any]:
    """Grab a single still from a Bandung pelindung CCTV camera."""
    cam = CAMERAS.get(camera_id)
    if not cam:
        return {"error": f"unknown camera {camera_id}", "known": list(CAMERAS)}

    browser = await _get_browser()
    ctx = await browser.new_context(viewport={"width": 1280, "height": 720})
    page = await ctx.new_page()
    try:
        await page.goto(cam["url"], wait_until="networkidle", timeout=20_000)
        # Many ATCS-style streams render into a <video> or <canvas>. Grab the
        # whole viewport — vision-mcp can crop later if needed.
        ts = int(time.time())
        out = PHOTOS_DIR / camera_id / f"{ts}.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(out), full_page=False, type="jpeg", quality=80)
        return {"path": str(out), "ts": ts, "camera_id": camera_id, "area": cam["area"]}
    except Exception as e:
        return {"error": str(e), "camera_id": camera_id}
    finally:
        await ctx.close()


@mcp.tool()
async def list_cameras(near_lat: float | None = None, near_lon: float | None = None,
                       radius_km: float = 5.0) -> list[dict[str, Any]]:
    """List all known cameras, optionally filtered to those within radius_km."""
    if near_lat is None or near_lon is None:
        return list(CAMERAS.values())
    # cheap haversine-ish; for 5km in Bandung the equirectangular approx is fine
    out = []
    for cam in CAMERAS.values():
        dx = (cam["lon"] - near_lon) * 111 * 0.6  # cos(7°) ~ 0.99 → use 0.6 to be conservative
        dy = (cam["lat"] - near_lat) * 111
        if (dx * dx + dy * dy) ** 0.5 <= radius_km:
            out.append(cam)
    return out


# ─────────────────────────────────────────────────────────────────────────
# MARKETPLACE
# ─────────────────────────────────────────────────────────────────────────
_SEARCH_URLS = {
    "tokopedia": "https://www.tokopedia.com/search?st=product&q={q}",
    "olx":       "https://www.olx.co.id/items/q-{q}",
}


@mcp.tool()
async def marketplace_search(platform: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search a marketplace for listings matching `query`. Returns up to `limit` results."""
    if platform not in _SEARCH_URLS:
        return [{"error": f"unknown platform {platform}"}]

    url = _SEARCH_URLS[platform].format(q=query.replace(" ", "+" if platform == "tokopedia" else "-"))
    browser = await _get_browser()
    ctx = await browser.new_context(user_agent=(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124 Safari/537.36"
    ))
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25_000)
        await page.wait_for_timeout(2000)  # let lazy-loaded cards render

        # Generic, brittle selectors — refine per platform during H3-H7.
        if platform == "tokopedia":
            cards = await page.query_selector_all('[data-testid="divProductWrapper"]')
        else:  # olx
            cards = await page.query_selector_all('a[data-aut-id="itemBox"]')

        results: list[dict[str, Any]] = []
        for card in cards[:limit]:
            try:
                href = await card.get_attribute("href")
                text = (await card.inner_text()).strip()
                img_el = await card.query_selector("img")
                img_url = await img_el.get_attribute("src") if img_el else None
                # Naive parse — title = first line, price = first "Rp ..." match.
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                title = lines[0] if lines else ""
                price_match = re.search(r"Rp[\s\.\d]+", text)
                price = price_match.group(0) if price_match else None
                location = next((l for l in lines if any(k in l.lower() for k in ("bandung", "jabar", "jawa barat"))), None)
                results.append({
                    "url": href if href and href.startswith("http") else f"https://www.{platform}.co.id{href or ''}",
                    "title": title,
                    "price": price,
                    "image_url": img_url,
                    "location": location,
                    "platform": platform,
                })
            except Exception:
                continue
        return results
    except Exception as e:
        return [{"error": str(e), "platform": platform, "query": query}]
    finally:
        await ctx.close()


@mcp.tool()
async def marketplace_get_listing(url: str) -> dict[str, Any]:
    """Fetch a listing detail page and download its images for vision matching."""
    browser = await _get_browser()
    ctx = await browser.new_context()
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25_000)
        await page.wait_for_timeout(1500)
        title = await page.title()
        body_text = await page.inner_text("body")
        price_match = re.search(r"Rp[\s\.\d]+", body_text)
        price = price_match.group(0) if price_match else None

        # Download up to 5 images.
        slug = _slug(urlparse(url).path) or "listing"
        out_dir = PHOTOS_DIR / "listings" / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        img_paths: list[str] = []
        srcs: list[str] = []
        for img in (await page.query_selector_all("img"))[:20]:
            src = await img.get_attribute("src")
            if src and src.startswith("http") and src not in srcs:
                srcs.append(src)
            if len(srcs) >= 5:
                break
        for i, src in enumerate(srcs):
            try:
                resp = await ctx.request.get(src, timeout=10_000)
                if resp.ok:
                    p = out_dir / f"{i}.jpg"
                    p.write_bytes(await resp.body())
                    img_paths.append(str(p))
            except Exception:
                continue

        return {
            "url": url,
            "title": title,
            "price": price,
            "description": body_text[:2000],  # truncate, agent can ask for more
            "images": img_paths,
        }
    except Exception as e:
        return {"error": str(e), "url": url}
    finally:
        await ctx.close()


if __name__ == "__main__":
    mcp.run()
