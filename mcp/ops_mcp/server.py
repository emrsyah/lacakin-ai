"""ops-mcp: report rendering, Telegram media delivery, and visible heartbeats."""
from __future__ import annotations

import asyncio
import json
import os
import re
import textwrap
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP

SHARED_DIR = Path(os.environ.get("LACAKIN_SHARED", str(Path.home() / "lacakin" / "shared")))
REPORT_DIR = SHARED_DIR / "reports"
STATUS_DIR = SHARED_DIR / "status"
PREVIEW_DIR = SHARED_DIR / "photos" / "previews"
SHARED_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)
STATUS_DIR.mkdir(parents=True, exist_ok=True)
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

GROUP_ID = os.environ.get("LACAKIN_GROUP_ID", "")
TOKEN_ENV = {
    "orchestrator": "TELEGRAM_TOKEN_ORCHESTRATOR",
    "cctv": "TELEGRAM_TOKEN_CCTV",
    "marketplace": "TELEGRAM_TOKEN_MARKETPLACE",
    "parts": "TELEGRAM_TOKEN_PARTS",
    "sosmed": "TELEGRAM_TOKEN_SOSMED",
    "polisi": "TELEGRAM_TOKEN_POLISI",
    "report": "TELEGRAM_TOKEN_REPORT",
}

mcp = FastMCP("ops-mcp")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_name(value: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in value).strip("-") or "lacakin"


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap_markdown(markdown: str, width: int = 92) -> list[str]:
    lines: list[str] = []
    for raw in markdown.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if not line:
            lines.append("")
            continue
        prefix = ""
        text = line
        if line.startswith("# "):
            prefix, text = "", line[2:]
            lines.append(text.upper())
            continue
        if line.startswith("## "):
            prefix, text = "", line[3:]
            lines.append("")
            lines.append(text)
            continue
        if line.startswith("- "):
            prefix, text = "- ", line[2:]
        wrapped = textwrap.wrap(text, width=width, subsequent_indent="  ")
        if wrapped:
            lines.extend(prefix + chunk if idx == 0 else "  " + chunk for idx, chunk in enumerate(wrapped))
        else:
            lines.append(prefix)
    return lines


def _build_pdf(markdown: str, title: str) -> bytes:
    lines = _wrap_markdown(markdown)
    pages = [lines[i : i + 46] for i in range(0, len(lines), 46)] or [[title]]
    objects: list[bytes] = [
        b"",
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",  # pages tree, filled after page ids are known
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    page_ids: list[int] = []

    font_id = 3
    for page in pages:
        content_lines = ["BT", "/F1 10 Tf", "50 790 Td", "14 TL"]
        content_lines.append(f"({_pdf_escape(title)}) Tj")
        content_lines.append("T*")
        for line in page:
            content_lines.append(f"({_pdf_escape(line[:160])}) Tj")
            content_lines.append("T*")
        content_lines.append("ET")
        stream = "\n".join(content_lines).encode("latin-1", "replace")
        content_id = len(objects)
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
        page_id = len(objects)
        page_ids.append(page_id)
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>".encode()
        )

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj_id in range(1, len(objects)):
        offsets.append(len(pdf))
        pdf.extend(f"{obj_id} 0 obj\n".encode())
        pdf.extend(objects[obj_id])
        pdf.extend(b"\nendobj\n")
    xref_at = len(pdf)
    pdf.extend(f"xref\n0 {len(objects)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(objects)} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode())
    return bytes(pdf)


def _token(agent_id: str) -> str:
    env_name = TOKEN_ENV.get(agent_id, "")
    return os.environ.get(env_name, "")


def _telegram(method: str, agent_id: str, fields: dict[str, str], files: dict[str, Path] | None = None) -> dict[str, Any]:
    token = _token(agent_id)
    if not token:
        return {"ok": False, "error": f"missing token env for {agent_id}"}
    url = f"https://api.telegram.org/bot{token}/{method}"
    if not files:
        body = urllib.parse.urlencode(fields).encode()
        req = urllib.request.Request(url, data=body)
    else:
        boundary = "lacakin-boundary"
        chunks: list[bytes] = []
        for key, value in fields.items():
            chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode())
        for key, path in files.items():
            data = path.read_bytes()
            chunks.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"; filename=\"{path.name}\"\r\n"
                f"Content-Type: application/octet-stream\r\n\r\n".encode()
            )
            chunks.append(data + b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode())
        req = urllib.request.Request(url, data=b"".join(chunks), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:  # pragma: no cover - network depends on deployment
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def render_report_pdf(case_id: str, markdown: str, title: str | None = None) -> dict[str, Any]:
    """Render report Markdown into a simple PDF under shared/reports."""
    title = title or f"Laporan Lacakin - {case_id}"
    out = REPORT_DIR / f"{_safe_name(case_id)}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.pdf"
    out.write_bytes(_build_pdf(markdown, title))
    md_path = REPORT_DIR / f"{_safe_name(case_id)}-latest.md"
    md_path.write_text(markdown, encoding="utf-8")
    return {"case_id": case_id, "pdf_path": str(out), "markdown_path": str(md_path), "bytes": out.stat().st_size}


def _build_pdf_reportlab(markdown: str, title: str, out_path: Path) -> None:
    """Render markdown into a styled PDF via the anthropics `pdf` skill recipe.

    Mirrors the Platypus example in skills/pdf/SKILL.md: SimpleDocTemplate +
    getSampleStyleSheet, with basic `# / ## / -` markdown handling and UTF-8
    text (so Indonesian copy renders correctly, unlike the latin-1 fallback)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem,
    )

    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    h1 = ParagraphStyle("Lacakin-H1", parent=styles["Heading1"], spaceBefore=4, spaceAfter=10)
    h2 = ParagraphStyle("Lacakin-H2", parent=styles["Heading2"], spaceBefore=10, spaceAfter=6)
    meta = ParagraphStyle("Lacakin-Meta", parent=body, textColor="#666666", fontSize=9, spaceAfter=12)

    def _escape(text: str) -> str:
        return (text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"))

    story: list[Any] = [Paragraph(_escape(title), h1),
                        Paragraph(f"Generated {_now()}", meta)]
    bullets: list[Any] = []

    def _flush_bullets() -> None:
        if bullets:
            story.append(ListFlowable(
                [ListItem(Paragraph(_escape(b), body), leftIndent=12) for b in bullets],
                bulletType="bullet", start="•",
            ))
            bullets.clear()

    for raw in markdown.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if not line:
            _flush_bullets()
            story.append(Spacer(1, 4))
            continue
        if line.startswith("# "):
            _flush_bullets()
            story.append(Paragraph(_escape(line[2:]), h1))
        elif line.startswith("## "):
            _flush_bullets()
            story.append(Paragraph(_escape(line[3:]), h2))
        elif line.startswith("- "):
            bullets.append(line[2:])
        else:
            _flush_bullets()
            story.append(Paragraph(_escape(line), body))
    _flush_bullets()

    SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=title, author="Lacakin",
    ).build(story)


@mcp.tool()
def render_report_pdf_skill(case_id: str, markdown: str, title: str | None = None) -> dict[str, Any]:
    """Render report Markdown into a styled PDF using the anthropics `pdf` skill
    (reportlab/Platypus). Preferred over `render_report_pdf` — handles UTF-8,
    headings, and bullets properly. Falls back automatically if reportlab is
    unavailable.

    Same return shape as `render_report_pdf`."""
    title = title or f"Laporan Lacakin - {case_id}"
    out = REPORT_DIR / f"{_safe_name(case_id)}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.pdf"
    md_path = REPORT_DIR / f"{_safe_name(case_id)}-latest.md"
    md_path.write_text(markdown, encoding="utf-8")
    renderer = "reportlab"
    try:
        _build_pdf_reportlab(markdown, title, out)
    except ImportError:
        out.write_bytes(_build_pdf(markdown, title))
        renderer = "fallback-builtin"
    return {
        "case_id": case_id,
        "pdf_path": str(out),
        "markdown_path": str(md_path),
        "bytes": out.stat().st_size,
        "renderer": renderer,
    }


@mcp.tool()
def send_telegram_document(agent_id: str, file_path: str, caption: str = "", chat_id: str | None = None) -> dict[str, Any]:
    """Send a file as a Telegram document using one of the configured Lacakin bot tokens."""
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return {"ok": False, "error": f"file not found: {file_path}"}
    return _telegram("sendDocument", agent_id, {"chat_id": chat_id or GROUP_ID, "caption": caption[:1024]}, {"document": path})


@mcp.tool()
def send_telegram_photo(agent_id: str, image_path: str, caption: str = "", chat_id: str | None = None) -> dict[str, Any]:
    """Send an image finding to Telegram using one of the configured Lacakin bot tokens."""
    path = Path(image_path)
    if not path.exists() or not path.is_file():
        return {"ok": False, "error": f"image not found: {image_path}"}
    return _telegram("sendPhoto", agent_id, {"chat_id": chat_id or GROUP_ID, "caption": caption[:1024]}, {"photo": path})


def _preview_slug(url: str) -> str:
    parsed = urlparse(url)
    base = f"{parsed.netloc}{parsed.path}"
    return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")[:60] or "preview"


async def _screenshot_url(url: str, out_path: Path, viewport: str, wait_ms: int) -> None:
    """Headless-Chromium navigate + screenshot. Playwright is already a dep."""
    from playwright.async_api import async_playwright

    w, _, h = viewport.partition("x")
    width, height = int(w), int(h or 800)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            ctx = await browser.new_context(viewport={"width": width, "height": height})
            page = await ctx.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=25_000)
                if wait_ms > 0:
                    await page.wait_for_timeout(wait_ms)
                await page.screenshot(path=str(out_path), full_page=False, type="jpeg", quality=82)
            finally:
                await ctx.close()
        finally:
            await browser.close()


@mcp.tool()
def send_link_preview(
    agent_id: str,
    url: str,
    caption: str = "",
    viewport: str = "1280x800",
    wait_ms: int = 2500,
    chat_id: str | None = None,
) -> dict[str, Any]:
    """Open `url` in a headless Chromium tab, take a viewport screenshot, and post
    it to the Telegram group via the agent's own bot. Use this when you want the
    group to *see* what an agent is looking at (live CCTV frame, FB result page,
    listing page) without writing a finding row.

    The caption is auto-prefixed with the URL so users can click through:
        "<caption>\\n🔗 <url>"

    Returns {ok, screenshot_path, url, telegram}.
    """
    if not url or not url.lower().startswith(("http://", "https://")):
        return {"ok": False, "error": f"invalid url: {url!r}"}
    ts = int(time.time())
    out = PREVIEW_DIR / f"{ts}_{_preview_slug(url)}.jpg"
    try:
        asyncio.run(_screenshot_url(url, out, viewport, wait_ms))
    except RuntimeError:
        # Already inside a running loop (e.g. FastMCP async context).
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_screenshot_url(url, out, viewport, wait_ms))
        finally:
            loop.close()
    except Exception as exc:
        return {"ok": False, "error": f"screenshot failed: {exc}", "url": url}

    if not out.exists() or out.stat().st_size == 0:
        return {"ok": False, "error": "screenshot produced empty file", "url": url}

    full_caption = f"{caption}\n🔗 {url}".strip() if caption else f"🔗 {url}"
    tg = _telegram(
        "sendPhoto", agent_id,
        {"chat_id": chat_id or GROUP_ID, "caption": full_caption[:1024]},
        {"photo": out},
    )
    return {
        "ok": bool(tg.get("ok", False)),
        "screenshot_path": str(out),
        "url": url,
        "telegram": tg,
    }


@mcp.tool()
def post_heartbeat_status(agent_id: str, status: str, case_id: str = "default", chat_id: str | None = None, visible: bool = False) -> dict[str, Any]:
    """Record heartbeat status and optionally post a compact Telegram status line."""
    payload = {"agent_id": agent_id, "case_id": case_id, "status": status[:1000], "updated_at": _now()}
    path = STATUS_DIR / f"{_safe_name(agent_id)}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if not visible:
        return {"ok": True, "posted": False, "status_path": str(path)}
    text = f"[{agent_id}] {status[:350]}"
    result = _telegram("sendMessage", agent_id, {"chat_id": chat_id or GROUP_ID, "text": text})
    result["status_path"] = str(path)
    return result


if __name__ == "__main__":
    mcp.run()
