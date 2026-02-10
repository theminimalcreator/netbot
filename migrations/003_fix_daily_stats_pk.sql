-- Migration: Fix daily_stats primary key
-- Description: The old PK was on (date) only, which conflicts with the new 
-- multi-platform design. This replaces it with a composite PK on (date, platform).

-- Drop the old primary key (date only)
ALTER TABLE daily_stats DROP CONSTRAINT daily_stats_pkey;

-- Create composite primary key on (date, platform)
ALTER TABLE daily_stats ADD PRIMARY KEY (date, platform);

-- Drop the now-redundant unique constraint from migration 001
-- (the PK already enforces uniqueness on date+platform)
ALTER TABLE daily_stats DROP CONSTRAINT IF EXISTS daily_stats_date_platform_key;
