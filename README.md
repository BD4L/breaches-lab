# Breaches Lab

Staging mirror of the breach data aggregator. **This repository is not production.**

It exists so that scraper changes, schema migrations and dashboard work can be tested without
touching the live site or the live database. See [Relationship to production](#relationship-to-production)
before running anything here.

## What this project does

It collects public data-breach notifications from government portals, regulatory filings, vendor
APIs and security news feeds, normalises them into a single Postgres schema, and serves them as a
searchable dashboard.

- **24 scrapers** covering 16 state Attorney General portals, federal sources (SEC EDGAR 8-K,
  HHS OCR), APIs (Have I Been Pwned), and security news RSS feeds.
- **Supabase Postgres** as the datastore, written by scrapers with a service key and read by the
  browser with an anon key.
- **Astro + React + Tailwind** frontend, built to static files and published to GitHub Pages.
- **GitHub Actions** for orchestration, on cron schedules.

## Repository layout

```
scrapers/              One module per source, plus shared logging and change tracking
utils/                 Supabase client wrapper used by every scraper
frontend/              Astro + React dashboard (34 components)
  src/lib/             Supabase queries and formatting helpers
  src/components/      Dashboard, filters, breach detail, shared UI
supabase/functions/    Edge Functions for report generation
.github/workflows/     6 workflows (see below)
docs/                  Per-scraper implementation notes
database_schema*.sql   Table definitions and migrations
config.yaml            RSS feeds and per-source settings
```

## Workflows

| Workflow | Schedule | Purpose |
| --- | --- | --- |
| `paralell.yml` | every 30 min | Runs most scrapers, grouped into parallel jobs |
| `california-ag-scraper.yml` | hourly | California AG, with before/after database snapshots |
| `rss-api-scrapers.yml` | every 2 h | News feeds and API sources |
| `daily-report.yml` | daily 01:00 UTC | Activity summary and email alerts |
| `cali.yml` | every 30 min | Legacy; overlaps `paralell.yml` |
| `deploy-frontend.yml` | on push to `frontend/**` | Builds and publishes the dashboard |

**All scheduled workflows are disabled in this repository by default.** They were disabled
deliberately so that a fresh clone does not immediately start scraping government sites or writing
to a database. Enable individually from the Actions tab when you intend to test one.

## Local setup

### Scrapers

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export SUPABASE_URL="https://<project>.supabase.co"
export SUPABASE_SERVICE_KEY="<service-role-key>"
python scrapers/fetch_delaware_ag.py
```

Scrapers write to `scraped_items`, keyed on a unique `item_url`. Most skip rows that already exist
rather than updating them.

### Frontend

```bash
cd frontend
npm ci
cp .env.example .env.local     # fill in the two PUBLIC_SUPABASE_* values
npm run dev
```

`npm run build` produces static output in `frontend/dist`.

## Configuration

Scrapers read connection details from the environment:

| Variable | Used by | Notes |
| --- | --- | --- |
| `SUPABASE_URL` | all scrapers | Project REST URL |
| `SUPABASE_SERVICE_KEY` | all scrapers | Service role key. Server-side only, never in the frontend |
| `PUBLIC_SUPABASE_URL` | frontend | Inlined into the browser bundle at build time |
| `PUBLIC_SUPABASE_ANON_KEY` | frontend | Inlined into the browser bundle at build time |

Anything prefixed `PUBLIC_` is compiled into the published JavaScript and is readable by any
visitor. Only put values there that are safe to disclose, and rely on row level security rather
than key secrecy to protect the database.

## Relationship to production

Production lives in a separate repository and deploys to its own GitHub Pages site. This mirror was
created from production's `main` branch.

Differences that are intentional and should not be copied back:

- Scheduled workflows are disabled here.
- No Actions secrets are configured, so scrapers and deploys are inert until you add them.

Two cautions when testing:

1. **Database.** The scrapers point at whatever `SUPABASE_URL` you give them. If you supply the
   production project's credentials, this repository will write to production data. Use a separate
   Supabase project for testing.
2. **Source sites.** The scrapers hit live government portals. Re-enabling the 30-minute schedules
   here means those sites get scraped twice as often in total, from two repositories at once.

## Known issues

Carried over from production and not yet fixed:

- The California AG scraper enriches every record (listing fetch, detail page, PDF parse) before
  checking whether the record already exists, so an hourly run cannot finish within the hour.
- Several scrapers hardcode 2025 URLs or filter dates and cannot see current-year breaches.
- Dashboard aggregates are computed in the browser over a capped row fetch, so totals are both
  inaccurate and expensive in egress.
- Search text is interpolated directly into a PostgREST filter, so a comma or parenthesis in a
  query returns an error instead of results.
