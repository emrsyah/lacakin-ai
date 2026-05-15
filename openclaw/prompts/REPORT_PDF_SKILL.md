# Report PDF Skill

The report agent renders `./shared/REPORT.md` into a styled PDF via the
anthropics **pdf** skill (installed by `setup_vps.sh` with
`npx skills add https://github.com/anthropics/skills --skill pdf`).

You do **not** call the skill directly. The skill's reportlab/Platypus recipe
is wrapped behind one MCP tool in `ops-mcp`:

```
lacakin-ops-mcp__render_report_pdf_skill(case_id, markdown, title?)
  → { case_id, pdf_path, markdown_path, bytes, renderer }
```

`renderer` is either `"reportlab"` (skill path, preferred — UTF-8 safe, real
headings + bullets) or `"fallback-builtin"` (the older hand-rolled PDF in
ops_mcp, used only if reportlab fails to import).

## Markdown features the renderer understands

- `# Heading` → page-level title
- `## Section` → section heading
- `- bullet`  → bulleted list (consecutive lines grouped automatically)
- Anything else → body paragraph
- Blank line → vertical space

Keep the markdown structure compatible with the template in
`./SYSTEM.md` (Ringkasan / Sightings CCTV / Marketplace / Parts /
Rekomendasi). Plain text inside bullets is fine; do **not** rely on inline
`**bold**`, links, or tables — they pass through unrendered.

## When to fall back

If `render_report_pdf_skill` returns `renderer="fallback-builtin"`, the PDF
will still send, but the formatting will be much plainer. Log this in your
heartbeat status so an operator can investigate the missing reportlab dep —
**do not** retry, just report and continue.

Only call the older `render_report_pdf` directly if the skill tool itself
errors out entirely.
