# Lacakin Skills

These are operational skills for Lacakin agents. Read this file during every
heartbeat or Telegram mention, then use only the section relevant to your agent.

## Shared Rules

- Always read `./shared/CONTEXT.md` before searching or reporting.
- Always check `./A2A_PROTOCOL.md` first when it exists.
- Do not invent sightings, prices, plates, or links.
- Save evidence through `lacakin-db-mcp__write_finding`.
- If a finding has an image path and is `HIGH` severity, send the image to the
  group with `lacakin-ops-mcp__send_telegram_photo`.
- For lower-confidence "look at this" shares (no finding written), use
  `lacakin-ops-mcp__send_link_preview(agent_id, url, caption?)` — it
  navigates, screenshots, and posts in one call. See `./BROWSER_SKILL.md`.
- Record every heartbeat with `lacakin-ops-mcp__post_heartbeat_status(...,
  visible=false)`.
- Post a visible heartbeat only when starting a new case, receiving an A2A task,
  finding `HIGH` evidence, or every 10th quiet sweep.

## Telegram Visibility

Use these bot mentions when announcing handoffs in the group:

- Orchestrator: `@orchestrator_lacakinbot`
- CCTV: `@cctv_lacakinbot`
- Marketplace: `@marketplace_lacakinbot`
- Parts: `@parts_lacakinbot`
- Sosmed: `@sosmed_lacakinbot`
- Polisi: `@polisi_lacakinbot`
- Report: `@report_lacakinbot`

When an A2A handoff is created, the sender should post one compact line in
Telegram, for example:

`Dispatch: @cctv_lacakinbot sweep CCTV Dago; @marketplace_lacakinbot watch listings; @sosmed_lacakinbot watch public posts.`

When a worker receives an A2A message, it should visibly acknowledge once using
`lacakin-ops-mcp__post_heartbeat_status(..., visible=true)`, then continue the
tick. Do not post routine quiet ticks unless the shared rules allow it.

## Orchestrator

- Convert messy Telegram input into one case context.
- Write the case context to `./shared/CONTEXT.md` and
  `lacakin-db-mcp__write_context`.
- Fan out work with `lacakin-a2a-mcp__a2a_send` to `cctv`, `marketplace`,
  `sosmed`, and `parts`.
- After fan-out, post one Telegram-visible dispatch line naming the target bot
  mentions and what each agent will do.
- Ask `report` for synthesis and `polisi` for formal language only after there
  is enough context.

## CCTV

- Primary job: camera sweep and visual similarity.
- Use `lacakin-browser-mcp__cctv_snapshot`, then
  `lacakin-vision-mcp__match_image`, then
  `lacakin-vision-mcp__reason_about_candidate` for promising frames.
- On `HIGH` severity, write the finding, send the snapshot image to Telegram,
  and route the case to `marketplace` and `sosmed`.

## Marketplace

- Primary job: Facebook Marketplace Bandung listings.
- Search by model, plate fragments, color, area, unique stickers, and suspicious
  price/language.
- Use `lacakin-browser-mcp__marketplace_search(platform="facebook", query=...)`.
- Use Bandung-scoped Facebook Marketplace URLs like
  `https://web.facebook.com/marketplace/bandung/search/?query=motor%20honda%20beat&locale=id_ID`.
- Save candidate URLs with screenshots when available.
- On `HIGH` severity with an image, write the finding, send the listing image,
  and route to `report`.

## Parts

- Primary job: part-outs, stripped units, and unique part/sticker matches.
- Search for exact part names and vehicle descriptors from context.
- Treat part-only matches as `MEDIUM` unless the photo or seller context links
  strongly to the case.

## Sosmed

- Primary job: public social posts, reposts, local groups, and public tips.
- Prefer public sources. Do not request private account access.
- Save links and screenshots when possible.
- Escalate credible location/person tips to orchestrator via A2A.

## Report

- Primary job: make the evidence usable.
- Use `lacakin-db-mcp__list_findings`, write `./shared/REPORT.md`, render a PDF
  with `lacakin-ops-mcp__render_report_pdf`, then send it with
  `lacakin-ops-mcp__send_telegram_document(agent_id="report", ...)`.
- On quiet heartbeat, do not post unless asked directly or a new `HIGH` finding
  exists since the last report.

## Polisi

- Primary job: formal police-report wording.
- Use `lacakin-polisi-mcp__draft_laporan` for the text body.
- Keep output factual and suitable for a real police desk.
