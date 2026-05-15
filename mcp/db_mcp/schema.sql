CREATE TABLE IF NOT EXISTS cases (
    id           TEXT PRIMARY KEY,
    status       TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    context_md   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id      TEXT NOT NULL,
    agent_id     TEXT NOT NULL,             -- cctv-bandung, marketplace-tokopedia, ...
    severity     TEXT NOT NULL,             -- HIGH | MEDIUM | LOW
    score        REAL,
    source_url   TEXT,
    image_path   TEXT,
    note         TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    delivered    INTEGER NOT NULL DEFAULT 0 -- has orchestrator forwarded to user?
);

CREATE INDEX IF NOT EXISTS idx_findings_case   ON findings(case_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_findings_undelivered ON findings(case_id, delivered) WHERE delivered = 0;
