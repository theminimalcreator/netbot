-- Table: llm_logs
-- Stores detailed logs of all LLM interactions for auditing and debugging.
CREATE TABLE IF NOT EXISTS llm_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Context
    provider TEXT NOT NULL,         -- e.g., 'openai', 'anthropic'
    model TEXT NOT NULL,            -- e.g., 'gpt-4o-mini'
    
    -- Inputs
    system_prompt TEXT,             -- The system instructions used
    user_prompt TEXT NOT NULL,      -- The actual input/prompt sent
    parameters JSONB DEFAULT '{}'::JSONB, -- Temperature, max_tokens, etc.
    
    -- Outputs
    response TEXT,                  -- The raw response text
    
    -- Metrics
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_cost FLOAT,               -- Estimated cost in USD
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::JSONB -- context tags (post_id, platform, etc.)
);

-- Index for searching logs by metadata (e.g., find logs for a specific post_id)
CREATE INDEX IF NOT EXISTS idx_llm_logs_metadata ON llm_logs USING gin (metadata);
CREATE INDEX IF NOT EXISTS idx_llm_logs_created_at ON llm_logs(created_at);
