-- Dashboard aggregate helpers
--
-- Purpose: stop transferring the whole breach dataset to compute counts.
--
-- scrapers/database_change_tracker.py runs twice per workflow run, across three scheduled
-- workflows. Without these, each call paginates the whole of v_breach_dashboard and groups the
-- rows in Python, so the number of bytes leaving the database scales with the size of the table
-- and is paid roughly 140 times a day. On the Supabase free tier that allowance is 5 GB a month.
--
-- With the RPC below the same call returns one row per source, typically a few dozen rows.
--
-- Apply with:  psql "$DATABASE_URL" -f database_schema_dashboard_stats.sql
--          or: paste into the Supabase SQL Editor and run.

-- ---------------------------------------------------------------------------
-- Per-source aggregates, used by database_change_tracker.fetch_source_groups()
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_dashboard_stats()
RETURNS TABLE (
    source_type  text,
    source_name  text,
    item_count   bigint,
    affected_sum bigint
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        source_type::text,
        source_name::text,
        count(*)                                        AS item_count,
        coalesce(sum(affected_individuals), 0)::bigint  AS affected_sum
    FROM v_breach_dashboard
    GROUP BY source_type, source_name;
$$;

COMMENT ON FUNCTION get_dashboard_stats() IS
    'Per-source item counts and affected-individual sums for the dashboard. Returns one row per '
    'source so callers do not have to download the table to count it.';

-- The scrapers connect with the service role, which bypasses RLS and already has access.
-- Granting execute to anon/authenticated as well lets the frontend use the same aggregates
-- instead of counting rows in the browser.
GRANT EXECUTE ON FUNCTION get_dashboard_stats() TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- Supporting indexes
-- ---------------------------------------------------------------------------
-- The aggregate groups on these two columns, and the tracker separately counts rows by
-- scraped_at for its "recent" and "today" figures.
CREATE INDEX IF NOT EXISTS idx_scraped_items_source_id  ON scraped_items (source_id);
CREATE INDEX IF NOT EXISTS idx_scraped_items_scraped_at ON scraped_items (scraped_at DESC);

-- ---------------------------------------------------------------------------
-- Verification
-- ---------------------------------------------------------------------------
-- Should return one row per source, not one row per item:
--     SELECT * FROM get_dashboard_stats() ORDER BY item_count DESC;
--
-- Totals here must match what the dashboard reports:
--     SELECT sum(item_count) AS items, sum(affected_sum) AS affected FROM get_dashboard_stats();
