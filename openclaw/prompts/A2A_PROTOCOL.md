# A2A Protocol — every worker reads this every tick

## At the START of every tick

1. Call `lacakin-a2a-mcp__a2a_inbox(to_agent=<your_agent_id>)`. If non-empty:
   - These are pivot requests from other agents (or the user via @-mention).
   - Treat them as **the priority for THIS tick**, overriding your default plan.
   - For each message: apply its `reason` and `payload` to scope your sweep.
   - Call `lacakin-a2a-mcp__a2a_consume(message_ids=[...])` once you've integrated them.

## When you decide another agent should pivot

If your Sonnet vision call returns a non-empty `route_to`:

1. For each `{agent, reason}` in `route_to`:
   - Generate (or carry forward) `chain_id`.
   - Call `lacakin-a2a-mcp__a2a_send(case_id=<...>, from_agent=<you>, to_agent=<agent>,
     reason=<reason>, payload=<your sweep context>, chain_id=<...>)`.
2. Also append the visible `@<agent> — <reason>` line to your group post.

## At the END of every tick (no exceptions)

- Call `lacakin-a2a-mcp__a2a_tick_done(to_agent=<your_agent_id>)`.
  This decrements TTL of any inbox messages that weren't relevant this tick,
  so they don't re-fire forever.

## CRITICAL: How to post to Telegram group

**NEVER use the built-in `message` tool to reply** — your text output at the end
of a turn is automatically sent back through Telegram by OpenClaw.

To **proactively post** to the group (e.g. findings, status updates), use:
`lacakin-ops-mcp__post_heartbeat_status(agent_id=<your_id>, status=<text>, case_id=<id>, visible=true)`

Or for photos: `lacakin-ops-mcp__send_telegram_photo(agent_id=<your_id>, ...)`

Do NOT call `message(action="send", ...)` — it will fail.

## Hard rules

- Never `a2a_send` to yourself.
- Never `a2a_send` with the same `chain_id` to an agent already in that chain
  (the MCP enforces this — it'll drop silently — but don't generate them).
- The orchestrator alone can issue `close_case` actions. Workers never.
