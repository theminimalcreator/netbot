-- Table: publications
-- Tracks all content successfully published by the bot.
CREATE TABLE IF NOT EXISTS publications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_idea_id UUID REFERENCES content_ideas(id),
    platform TEXT NOT NULL,           -- 'twitter', 'threads', 'devto', etc.
    ext_post_id TEXT,                 -- ID returned by the platform
    published_text TEXT,               -- The final text that was posted
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for checking publication frequency/limits
CREATE INDEX IF NOT EXISTS idx_publications_platform_created ON publications(platform, created_at);
CREATE INDEX IF NOT EXISTS idx_publications_idea_id ON publications(content_idea_id);
