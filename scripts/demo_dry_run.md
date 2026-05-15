# Demo dry-run checklist (run T-30min before judging)

## Pre-flight (10 min)

- [ ] VPS reachable, time synced
- [ ] `.env` contains all 7 TELEGRAM_TOKEN_* + ANTHROPIC_API_KEY + LACAKIN_GROUP_ID
- [ ] `.env.demo` values correct (`cat .env.demo`)
- [ ] All 7 bots `getMe` returns expected username (run command from `botfather_checklist.md`)
- [ ] Telegram group has all 7 bots as admins
- [ ] **Bot-to-bot mention smoke** — confirms cross-bot @-mentions reach the mentioned bot's `getUpdates`. Critical for the visible-coordination wow layer.
  ```bash
  # Post from one bot, mentioning another:
  curl -s "https://api.telegram.org/bot$TELEGRAM_TOKEN_CCTV/sendMessage" \
       -d "chat_id=$LACAKIN_GROUP_ID" \
       -d "text=smoke: @cadang_bot please respond"
  sleep 2
  # Confirm the parts bot received it:
  curl -s "https://api.telegram.org/bot$TELEGRAM_TOKEN_PARTS/getUpdates" \
       | jq '.result[-1].message.text'
  ```
  Expected: prints `"smoke: @cadang_bot please respond"`. If empty or missing,
  re-run `@BotFather /setprivacy → Disable` on `@cadang_bot` and try again.
  If still empty, **fall back: drop visible @-mentions from prompts, rely on
  A2A inbox only** (the prompts can stay as-is; nothing else breaks).
- [ ] `python scripts/serve_demo_assets.py &` running; `curl http://localhost:8765/cctv_clips/dago-simpang.html` returns the HTML
- [ ] `python scripts/seed_demo.py` ran without error
- [ ] `python scripts/register_demo_fixtures.py` ran without error
- [ ] Smoke vision: `python -c "from mcp.vision_mcp.sonnet_reason import reason_about_candidate; print(reason_about_candidate('demo_assets/cctv_clips/staged-motor-frame.jpg','test','cctv'))"` returns the fixture response

## Start (5 min)

- [ ] `bash scripts/start_gateway.sh demo` — gateway boots, no error in logs
- [ ] All 7 agents show up in `openclaw status`
- [ ] All 7 bots are online (Telegram shows them as "online")

## Smoke through the flow (10 min)

- [ ] In the group, type a test message; `@lacakin_bot` responds in <5s
- [ ] Provide a full case in one message (motor, plat, lokasi, jam, ciri); orchestrator pins case context
- [ ] Within 5s, see Mata + Pasar + Sosmed + Cadang post opening lines (swarm awakening)
- [ ] Within 30-60s, Mata posts the staged CCTV finding with vision reasoning
- [ ] Pasar posts the staged Tokopedia finding within 45-90s
- [ ] @-mention from Mata to @cadang is visible; Cadang's next tick mentions "mengikuti arahan @mata"
- [ ] Type `@mata cek Pasteur sekarang`; Mata's next tick targets Pasteur (any image is fine)
- [ ] Type `@laporan rangkum sekarang`; report posted within 5s
- [ ] Type `@polisi tolong draft laporan`; draft posted within 5s

## Cleanup

- [ ] Stop gateway: Ctrl+C
- [ ] Reset for live demo: `python -c "from mcp.db_mcp.server import _conn; _conn.execute('DELETE FROM findings'); _conn.execute('UPDATE cases SET status=\"CLOSED\"')"`
- [ ] Verify group is clean (delete bot posts manually if you want)

## If anything fails

- See `docs/plans/2026-05-15-lacakin-openclaw-wow-design.md` Section 8 (Risks & cutlines)
- Specific recovery:
  - Bots offline → re-source `.env.demo`, restart gateway
  - No vision reasoning → `register_demo_fixtures.py` again
  - Group not receiving → re-promote bots to admin
  - Sonnet rate limited → demo proceeds on fixtures only, no real Sonnet calls
