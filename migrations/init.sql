-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table: interactions
-- Tracks every comment made by the bot to ensure we don't spam/duplicate.
CREATE TABLE IF NOT EXISTS interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    post_id TEXT NOT NULL UNIQUE,  -- Instagram Post ID (Media PK)
    username TEXT NOT NULL,        -- Author of the post
    comment_text TEXT NOT NULL,    -- The text we posted
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::JSONB -- Extra info (sentiment, reasoning)
);

-- Table: daily_stats
-- Simple counter to enforce daily limits safely.
CREATE TABLE IF NOT EXISTS daily_stats (
    date DATE PRIMARY KEY DEFAULT CURRENT_DATE,
    interaction_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table: logs
-- Structured application logs.
CREATE TABLE IF NOT EXISTS logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    level TEXT NOT NULL, -- INFO, ERROR, WARNING
    module TEXT NOT NULL, -- discovery, brain, etc.
    message TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for faster lookups on interactions
CREATE INDEX IF NOT EXISTS idx_interactions_username ON interactions(username);
CREATE INDEX IF NOT EXISTS idx_interactions_created_at ON interactions(created_at);
