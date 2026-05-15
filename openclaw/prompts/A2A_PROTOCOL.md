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

## Hard rules

- Never `a2a_send` to yourself.
- Never `a2a_send` with the same `chain_id` to an agent already in that chain
  (the MCP enforces this — it'll drop silently — but don't generate them).
- The orchestrator alone can issue `close_case` actions. Workers never.
