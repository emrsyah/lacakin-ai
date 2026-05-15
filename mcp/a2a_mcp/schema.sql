CREATE TABLE IF NOT EXISTS a2a_messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id     TEXT NOT NULL,        -- UUID, identifies a pivot chain
    case_id      TEXT NOT NULL,
    from_agent   TEXT NOT NULL,
    to_agent     TEXT NOT NULL,
    reason       TEXT NOT NULL,
    payload_json TEXT NOT NULL,        -- arbitrary JSON the receiver consumes
    ttl_ticks    INTEGER NOT NULL,     -- decremented by receiver each tick
    created_at   TEXT NOT NULL,
    consumed_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_a2a_inbox ON a2a_messages(to_agent, consumed_at);
CREATE INDEX IF NOT EXISTS idx_a2a_chain ON a2a_messages(chain_id);
