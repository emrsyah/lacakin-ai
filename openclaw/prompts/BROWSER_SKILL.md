# Browser Skill

This workspace has access to the `agent-browser` skill (Vercel Labs). When the
MCP browser tools are not a perfect fit (e.g. you need a *whole-page* screenshot
of a specific URL for visual matching), drive the browser via the skill:

```bash
npx agent-browser screenshot \
  --url "<URL>" \
  --out "<absolute_path>.jpg" \
  --viewport 1280x800 \
  --wait-ms 2500
```

The CLI is invokable as `npx agent-browser ...` even when the package is not
installed globally.

## When to prefer the MCP tools

Prefer Lacakin MCP first when they cover the job — they handle workspace paths,
photo dirs, and dedup wiring for you:

- `lacakin-browser-mcp__cctv_snapshot(camera_id)` — single still from a
  pelindung Bandung camera (snapshot saved under `shared/photos/<camera>/`).
- `lacakin-browser-mcp__marketplace_search(platform="facebook", query=...)`
- `lacakin-browser-mcp__marketplace_get_listing(url)`

## Target URLs (focus areas)

- **CCTV** — all entries in `./cameras.json` resolve into
  `https://pelindung.bandung.go.id/cctv/<id>`. That portal is the canonical
  source for Bandung public CCTV — do not invent other camera hosts.
- **Sosmed (Facebook)** — use the top-search URL pattern:
  `https://web.facebook.com/search/top/?q=<query>&locale=id_ID`
  Example: `https://web.facebook.com/search/top/?q=honda%20beat%20jual%20bu&locale=id_ID`.
  Do **not** use `/marketplace/...` paths in the sosmed agent — that workspace
  belongs to the `marketplace` agent.

## Two-stage match recipe (CCTV + sosmed)

1. Use `agent-browser screenshot` (or the appropriate MCP) to capture the page
   to a local `.jpg`.
2. Score the screenshot against the relevant **text** with
   `lacakin-vision-mcp__match_text_image(text=<query_or_case>, image_path=<jpg>)`:
   - CCTV: `text = <case description from CONTEXT.md>` (merk/model/warna/plat).
   - Sosmed: `text = <FB search query string>` (e.g. `"honda beat jual bu"`).
3. Only when `score >= 0.25` (text↔image cosines run lower than image↔image),
   escalate to `lacakin-vision-mcp__reason_about_candidate(image_path,
   context_md, source_type=<"cctv"|"social">)` for the structured verdict.

## Sharing a live link preview with the group

When you want the Telegram group to *see* the page you're on (e.g. a CCTV
frame, an FB top-search result page, a marketplace listing) **without**
filing a finding row, use:

```
lacakin-ops-mcp__send_link_preview(
  agent_id="<your id>",
  url="<full URL>",
  caption="<one short Indonesian sentence — optional>",
  viewport="1280x800",   # default; use "1280x1600" for long FB feeds
  wait_ms=2500,          # bump to 4000 for slow pages
)
```

This is a single tool call — it screenshots headless, ships the image with
the URL auto-appended to the caption, and returns `{ok, screenshot_path}`.

When to call it:
- An A2A pivot tells you to "show me" — reply with `send_link_preview` of
  the candidate page instead of pasting a raw URL.
- You hit a `0.18–0.25` text-image score (interesting but not HIGH). A
  preview lets the operator make the call without you escalating to Stage 2.

When **not** to call it:
- On every tick. This costs a browser context per call.
- For HIGH findings — those already include the snapshot via
  `send_telegram_photo` + `write_finding`. Don't double-post.

## Block / login behaviour

If `pelindung.bandung.go.id` returns no frame or Facebook serves a login wall /
CAPTCHA, **do not fabricate findings**. Report `BLOCKED_PELINDUNG` /
`BLOCKED_FACEBOOK` in your heartbeat status and preserve the URL + screenshot
path for manual review.
