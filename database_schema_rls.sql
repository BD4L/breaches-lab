-- Row Level Security and Data API grants
--
-- Run this AFTER database_schema.sql (and any other schema files you apply).
-- Safe to re-run; every statement is idempotent and skips objects that do not exist.
--
-- WHY THIS EXISTS
--
-- The browser holds the anon key. It is compiled into the published JavaScript bundle and is
-- readable by every visitor — that is by design, and it is only safe if the database refuses to
-- do anything with that key beyond what an anonymous member of the public should be able to do.
-- Without RLS, the anon key can INSERT, UPDATE and DELETE every row in the database.
--
-- MODEL
--
--   deny by default        RLS on, no policy, no grant. Reachable only by service_role.
--   public read            SELECT for anon on the breach data the dashboard displays.
--   service_role           full access. It holds BYPASSRLS, so policies do not constrain the
--                          scrapers; they only need the grants below.
--
-- Anything not explicitly opened below stays closed, including tables added later.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Remove blanket access from the API roles
-- ---------------------------------------------------------------------------
-- Supabase's "automatically expose new tables" setting grants the API roles access to
-- everything in public. Start from nothing and re-grant deliberately.

REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon, authenticated;

-- New tables should not become readable just because someone created them.
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES    FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated;

-- The roles still need to see the schema itself to resolve names.
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- 2. Enable RLS on every table in public
-- ---------------------------------------------------------------------------
-- Loops rather than listing names, so tables from migrations not applied here — and any added
-- later — are covered too. A table with RLS on and no policy denies everything except
-- service_role, which is the correct default for this dataset.

DO $$
DECLARE t record;
BEGIN
    FOR t IN
        SELECT schemaname, tablename
        FROM pg_tables
        WHERE schemaname = 'public'
    LOOP
        EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY', t.schemaname, t.tablename);
        RAISE NOTICE 'RLS enabled: %', t.tablename;
    END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- 3. Public read on the breach data the dashboard displays
-- ---------------------------------------------------------------------------
-- These three carry published breach notifications and the list of sources they came from.
-- All of it is already public information republished from government portals.

DO $$
DECLARE
    obj text;
    public_read text[] := ARRAY['scraped_items', 'data_sources'];
BEGIN
    FOREACH obj IN ARRAY public_read LOOP
        IF to_regclass('public.' || obj) IS NULL THEN
            RAISE NOTICE 'skipping % (does not exist)', obj;
            CONTINUE;
        END IF;

        EXECUTE format('GRANT SELECT ON public.%I TO anon, authenticated', obj);

        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', obj || '_public_read', obj);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR SELECT TO anon, authenticated USING (true)',
            obj || '_public_read', obj
        );
        RAISE NOTICE 'public read granted: %', obj;
    END LOOP;
END $$;

-- The dashboard reads through this view rather than the base table.
--
-- security_invoker makes the view run with the caller's permissions. Without it a view executes
-- as its owner and bypasses RLS on the tables underneath, which would make the policies above
-- decorative: anyone could read everything through the view no matter what the base table said.
DO $$
BEGIN
    IF to_regclass('public.v_breach_dashboard') IS NOT NULL THEN
        EXECUTE 'ALTER VIEW public.v_breach_dashboard SET (security_invoker = on)';
        EXECUTE 'GRANT SELECT ON public.v_breach_dashboard TO anon, authenticated';
        RAISE NOTICE 'public read granted: v_breach_dashboard (security_invoker on)';
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 4. Service role keeps full access
-- ---------------------------------------------------------------------------
-- The scrapers authenticate with this key. It bypasses RLS, so it needs no policies, but it
-- does need grants.

GRANT ALL ON ALL TABLES    IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES    TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;

-- ---------------------------------------------------------------------------
-- 4b. Re-grant the dashboard aggregate function
-- ---------------------------------------------------------------------------
-- Step 1 revoked EXECUTE on every function in public, which includes get_dashboard_stats() if
-- database_schema_dashboard_stats.sql was applied first. Without this, running the two files in
-- that order would silently strip the grant and the frontend would fall back to counting rows in
-- the browser — the exact behaviour that function exists to replace. Guarded so it is a no-op
-- when the function has not been created.
--
-- It only returns aggregate counts over data that is already publicly readable.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = 'get_dashboard_stats'
    ) THEN
        EXECUTE 'GRANT EXECUTE ON FUNCTION public.get_dashboard_stats() TO anon, authenticated, service_role';
        RAISE NOTICE 'execute re-granted: get_dashboard_stats()';
    END IF;
END $$;

COMMIT;

-- ---------------------------------------------------------------------------
-- 5. What is deliberately NOT reachable from the browser
-- ---------------------------------------------------------------------------
-- Left denied on purpose. Each holds personal data or operational detail that an anonymous
-- visitor has no reason to read, and none of it is needed to render the dashboard.
--
--   user_prefs                  alert email addresses and verification status
--   email_verification_tokens   possession of a token is enough to confirm an address
--   alert_history               who was emailed about what
--   research_jobs               per-user report requests
--   ai_report_usage             per-user usage counters
--   scraper_runs / _progress    operational telemetry
--   scraper_errors / _activities
--   v_scraper_*                 views over that telemetry
--
-- Three frontend features touch these and will report errors after this runs. All three are
-- already broken, so this removes no working behaviour:
--
--   * Email preferences: EmailPreferences.tsx writes user_id = 'anonymous', but the column is
--     UUID REFERENCES auth.users. That upsert cannot succeed today. Restoring the feature needs
--     real Supabase Auth, then a policy of USING (auth.uid() = user_id) — not a public grant,
--     which would let any visitor read every subscriber's email address and redirect alerts.
--   * Saved breaches: queries saved_breaches, a table no schema file creates.
--   * AI reports: research_jobs / ai_report_usage are per-user and have no auth to scope them.

-- ---------------------------------------------------------------------------
-- 6. Verification
-- ---------------------------------------------------------------------------
-- Every table should report rls_enabled = true:
--
--     SELECT relname, relrowsecurity AS rls_enabled
--     FROM pg_class
--     WHERE relnamespace = 'public'::regnamespace AND relkind = 'r'
--     ORDER BY relname;
--
-- anon should hold SELECT and nothing else, on only the objects opened above:
--
--     SELECT table_name, privilege_type
--     FROM information_schema.role_table_grants
--     WHERE grantee = 'anon' AND table_schema = 'public'
--     ORDER BY table_name, privilege_type;
--
-- The definitive check is from outside the database. With ANON_KEY and PROJECT_URL set:
--
--     # should return rows
--     curl -s "$PROJECT_URL/rest/v1/scraped_items?select=id&limit=1" \
--          -H "apikey: $ANON_KEY" -H "Authorization: Bearer $ANON_KEY"
--
--     # should return an empty array or a permission error, NOT an email address
--     curl -s "$PROJECT_URL/rest/v1/user_prefs?select=email" \
--          -H "apikey: $ANON_KEY" -H "Authorization: Bearer $ANON_KEY"
--
--     # should be rejected — this is the hole this file closes
--     curl -s -X DELETE "$PROJECT_URL/rest/v1/scraped_items?id=eq.0" \
--          -H "apikey: $ANON_KEY" -H "Authorization: Bearer $ANON_KEY"
