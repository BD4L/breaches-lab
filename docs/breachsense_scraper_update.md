# BreachSense Scraper Update Documentation

**Updated:** May 31, 2025  
**Scraper:** `scrapers/fetch_breachsense.py`  
**Source ID:** 19  
**Website:** https://www.breachsense.com/breaches/

## Overview

The BreachSense scraper has been completely rewritten to handle the current website structure, which changed from a table-based layout to a card-based layout with individual breach detail pages.

## Key Changes

### 1. **New Scraping Approach**
- **Monthly Archive Strategy**:
  - Uses monthly archive URLs (e.g., `/breaches/2025/may/`) instead of main page
  - Extracts ALL breaches for the month (393+ breaches vs 12 on main page)
  - Two-Phase Processing: Extract breach cards Visit detail pages for comprehensive data

### 2. **Website Structure Handling**
- **Monthly Archives**: Accesses complete monthly breach listings
- **Comprehensive Coverage**: Captures all breaches instead of just recent ones
- **Detail Pages**: Extracts structured data from individual breach pages
- **Data Extraction**: Handles table-based data on detail pages with fallback parsing

### 3. **Enhanced Data Mapping**
- **Organization Name**: `title` field (uses victim name from detail page)
- **Breach Date**: `breach_date` field (text format) and `publication_date` (ISO format)
- **Leak Size**: Original format (e.g., "188GB") stored in `raw_data_json` - NO individual count estimation
- **Threat Actor**: Stored in `raw_data_json` and used for tagging
- **Size Category**: Categorizes leaks as small/medium/large/very_large for tagging
- **Description**: `what_was_leaked` field
- **Detail URL**: `item_url` field (links to specific breach page)

### 4. **Improved Data Processing**
- **Leak Size Categorization**: Categorizes data sizes (GB/TB) without estimating individual counts
- **Date Filtering**: Configurable date filtering to focus on recent breaches
- **Threat Actor Tagging**: Automatically creates tags from threat actor names
- **Size-Based Classification**: Tags breaches based on data size (small/medium/large/very_large data leaks)

### 5. **Configuration Options**
- `BREACHSENSE_FILTER_FROM_DATE`: Date filter - processes breaches from this date forward (default: today's date)
- `BREACHSENSE_PROCESSING_MODE`: BASIC, ENHANCED, FULL (default: "ENHANCED")
- `BREACHSENSE_MAX_BREACHES`: Limit for GitHub Actions (default: 50)

## Data Fields Populated

### Core Fields
- `source_id`: 19 (BreachSense)
- `item_url`: Individual breach detail page URL
- `title`: Organization/victim name
- `publication_date`: Date discovered (ISO format)
- `summary_text`: Comprehensive summary including threat actor and leak size

### Breach-Specific Fields
- `breach_date`: Date discovered (text format)
- `what_was_leaked`: Description of the organization/incident
- **Note**: `affected_individuals` field is NOT populated (BreachSense only provides data sizes, not individual counts)

### Metadata Fields
- `tags_keywords`: ["breachsense", "data_breach", "ransomware", threat_actor_name, size_category_tag]
- `raw_data_json`: Complete original data including threat actor, leak size, size category, description

## Sample Data Structure

```json
{
  "title": "ac-supply.com",
  "publication_date": "2025-05-30T00:00:00+00:00",
  "breach_date": "May 30, 2025",
  "affected_individuals": null,
  "what_was_leaked": "AC Supply Inc., a family-owned HVACR wholesale distributor...",
  "tags_keywords": ["large_data_leak", "breachsense", "data_breach", "ransomware", "interlock"],
  "raw_data_json": {
    "threat_actor": "Interlock",
    "leak_size_original": "188GB",
    "leak_size_category": "large",
    "description": "AC Supply Inc., a family-owned HVACR...",
    "detail_page_url": "https://www.breachsense.com/breaches/ac-supply-data-breach/",
    "original_date_string": "May 30, 2025"
  }
}
```

## Processing Modes

### BASIC Mode
- Extracts only basic information from breach cards
- No detail page scraping
- Faster processing, less comprehensive data

### ENHANCED Mode (Default)
- Scrapes detail pages for comprehensive information
- Extracts threat actor, leak size, description
- Balanced performance and data quality

### FULL Mode
- Complete analysis with all available features
- Most comprehensive data extraction
- Slower processing

## Error Handling

- **Rate Limiting**: 1-second delay between detail page requests
- **Graceful Degradation**: Continues processing if individual breaches fail
- **Duplicate Prevention**: Checks existing database entries before insertion
- **Comprehensive Logging**: Detailed logs for debugging and monitoring

## Performance Optimizations

- **Configurable Limits**: MAX_BREACHES setting for GitHub Actions
- **Date Filtering**: Only processes breaches from today forward (includes today + future dates)
- **Duplicate Checking**: Prevents re-processing existing breaches
- **Batch Processing**: Processes multiple breaches efficiently

## Testing Results

 **Monthly Archive Access**: Successfully extracts 393+ breach cards from monthly archive
 **Comprehensive Coverage**: Captures ALL monthly breaches vs 12 from main page
 **Detail Scraping**: Correctly parses structured data from detail pages
 **Database Integration**: Properly inserts data into all Supabase fields
 **Data Quality**: Accurate threat actor, leak size, and date information
 **Error Handling**: Robust error handling and logging

## GitHub Actions Integration

The scraper maintains full compatibility with the existing GitHub Actions workflow:
- Runs in the "News & API Scrapers" job
- Uses environment variables for configuration
- Respects timeout and resource limits
- Provides comprehensive logging for monitoring

## Future Enhancements

1. **Historical Data**: Option to scrape monthly archive pages
2. **Enhanced Parsing**: Improved extraction of data types compromised
3. **Threat Intelligence**: Integration with threat actor databases
4. **Notification System**: Alerts for high-impact breaches
