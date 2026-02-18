-- Migration: Create Dashboards Table
-- Description: Stores daily engagement cycle summaries and Telegram message references.

CREATE TABLE IF NOT EXISTS dashboards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    cycle_date DATE NOT NULL DEFAULT CURRENT_DATE,
    metrics JSONB NOT NULL,
    summary TEXT,
    telegram_message_id TEXT,
    
    -- Ensure only one dashboard per day per cycle (optional, but good for data integrity)
    -- If we run multiple cycles per day, we might want to include a cycle_run_id or similar if we had it.
    -- For now, let's just index the date for quick lookups.
    CONSTRAINT dashboards_cycle_date_key UNIQUE (cycle_date)
);

-- Add comment
COMMENT ON TABLE dashboards IS 'Stores daily engagement cycle summaries.';
