# Supabase Database Setup Guide

## URGENT: Database Tables Deleted - Quick Recovery

Your Supabase database tables were deleted, which is why the scrapers aren't populating data. Follow these steps to restore the complete database schema.

## Step-by-Step Recovery

### 1. Access Supabase SQL Editor
1. Go to your Supabase project dashboard
2. Click on **"SQL Editor"** in the left sidebar
3. Click **"New Query"** to create a new SQL script

### 2. Run the Database Schema Script
1. Copy the entire contents of `database_schema.sql` from this repository
2. Paste it into the Supabase SQL Editor
3. Click **"Run"** to execute the script

**What this creates:**
-`data_sources`table with all 37 breach portal sources
-`scraped_items`table with standardized cross-portal fields
- Performance indexes for fast querying
- All source mappings (SEC, State AGs, HIBP, etc.)

### 3. Verify Tables Created
After running the script, verify the tables exist:

```sql
-- Check data_sources table
SELECT COUNT(*) as source_count FROM data_sources;
-- Should return: 37

-- Check scraped_items table structure
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'scraped_items'
ORDER BY ordinal_position;

-- Verify source mappings
SELECT id, name, type FROM data_sources ORDER BY id;
```

### 4. Test Database Connection
Run a quick test to ensure everything works:

```sql
-- Test insert (will be cleaned up by scrapers)
INSERT INTO scraped_items (
    source_id, 
    item_url, 
    title, 
    publication_date, 
    summary_text
) VALUES (
    1, 
    'https://test.example.com/test', 
    'Test Entry', 
    NOW(), 
    'Database connection test'
);

-- Verify insert worked
SELECT * FROM scraped_items WHERE title = 'Test Entry';

-- Clean up test data
DELETE FROM scraped_items WHERE title = 'Test Entry';
```

## Database Schema Overview

### Core Tables

**`data_sources`** - Portal Information
- `id`: Source identifier (matches scraper configs)
- `name`: Human-readable source name
- `url`: Main portal URL
- `type`: Category (State AG, Government Portal, API, etc.)
- `description`: Brief description

**`scraped_items`** - Breach Records
- `id`: Auto-incrementing primary key
- `source_id`: Links to data_sources.id
- `item_url`: Unique URL (prevents duplicates)
- `title`: Organization/entity name
- `publication_date`: Primary date for sorting
- `summary_text`: Human-readable summary
- `raw_data_json`: Portal-specific data
- `tags_keywords`: Searchable tags array

**Standardized Cross-Portal Fields:**
- `affected_individuals`: Number of people affected
- `breach_date`: When incident occurred
- `reported_date`: When reported to authority
- `notice_document_url`: Link to official document

### Source ID Mapping

| ID | Source | Type |
|----|--------|------|
| 1 | SEC EDGAR 8-K | Government Portal |
| 2 | HHS OCR | Government Portal |
| 3-18 | State AG Portals | State AG |
| 19 | BreachSense | Breach Database |
| 20-29 | News Feeds | News Feed |
| 30 | Privacy Rights | Breach Database |
| 31-35 | Company IR | Company IR |
| 36 | HIBP API | API |
| 37 | Texas AG (Apify) | State AG |

## After Database Restoration

### 1. Trigger GitHub Actions
Once the database is restored:
1. Go to your GitHub repository
2. Click **"Actions"** tab
3. Click **"Run workflow"** on the main scraper workflow
4. Monitor the logs to see data being collected

### 2. Expected Results
After the workflow runs, you should see:
- Data in`scraped_items`table
- Breach records from multiple sources
- Standardized fields populated
- Cross-portal analysis possible

### 3. Verify Data Collection
Check that data is being collected:

```sql
-- Count records by source
SELECT 
    ds.name,
    COUNT(si.id) as record_count,
    MAX(si.scraped_at) as last_scraped
FROM data_sources ds
LEFT JOIN scraped_items si ON ds.id = si.source_id
GROUP BY ds.id, ds.name
ORDER BY ds.id;

-- Recent breach records
SELECT 
    title,
    affected_individuals,
    breach_date,
    ds.name as source
FROM scraped_items si
JOIN data_sources ds ON si.source_id = ds.id
WHERE si.scraped_at > NOW() - INTERVAL '1 day'
ORDER BY si.scraped_at DESC
LIMIT 20;
```

## Troubleshooting

### If Scrapers Still Fail
1. **Check Environment Variables**: Ensure `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are set
2. **Verify Permissions**: Ensure service key has read/write access
3. **Check Logs**: Look for specific error messages in GitHub Actions

### Common Issues
- **Foreign Key Violations**: Means data_sources table is missing entries
- **Unique Constraint Violations**: Normal - prevents duplicate entries
- **Connection Errors**: Check Supabase credentials

### Manual Data Source Addition
If you need to add a new source:

```sql
INSERT INTO data_sources (id, name, url, type, description) VALUES
(38, 'New Source Name', 'https://example.com', 'Source Type', 'Description');
```

## Success Indicators

You'll know the restoration worked when:
- GitHub Actions run without foreign key errors
- New records appear in`scraped_items`table
- Dashboard shows recent breach data
- Cross-portal queries return results

---

** The database schema includes all enhancements for standardized cross-portal analysis while maintaining backward compatibility with existing scrapers.**

**After running the schema script, your breach monitoring system will be fully operational again!**
