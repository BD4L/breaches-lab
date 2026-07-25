# Delaware AG Security Breach Scraper Documentation

## Overview
The Delaware Attorney General Security Breach Notification scraper extracts data breach information from the Delaware AG's public database of security breach notifications.

**Source URL**: https://attorneygeneral.delaware.gov/fraud/cpu/securitybreachnotification/database/

**Last Updated**: 2025-05-26

---

## Data Source Information

### Website Structure
- **Format**: HTML DataTable (no specific table ID)
- **Update Frequency**: Real-time as breaches are reported
- **Data Availability**: Public records of all breach notifications to Delaware AG
- **Historical Data**: Contains records dating back several years

### Table Columns (Current Structure)
1. **Organization Name** - Name of the entity that experienced the breach
2. **Date(s) of Breach** - When the actual security incident occurred
3. **Reported Date** - When the breach was reported to Delaware AG
4. **Number of Potentially Affected Delaware Residents** - Count of Delaware residents impacted
5. **Sample of Notice** - Link to PDF notification document

---

## Scraping Methods

### Technical Approach
- **HTTP Library**: `requests` with custom headers
- **HTML Parsing**: `BeautifulSoup4`
- **Date Parsing**: Custom `parse_date_delaware()` function with multiple format support
- **Error Handling**: Comprehensive fallback mechanisms to preserve all data

### Request Headers
```python
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
```

### Data Extraction Process
1. **Fetch Page**: GET request to main database URL
2. **Parse HTML**: Extract table using BeautifulSoup
3. **Process Rows**: Iterate through each `<tr>` in `<tbody>`
4. **Extract Fields**: Parse each column with specialized functions
5. **Data Validation**: Clean and validate extracted information
6. **Database Insert**: Store in Supabase with structured and raw data

---

## Data Collection Details

### What We Collect

#### Structured Database Fields
- **`title`**: Organization name (cleaned and extracted from potentially nested HTML)
- **`publication_date`**: Primary date for sorting (reported date preferred, breach date fallback)
- **`affected_individuals`**: Integer count of affected Delaware residents (when parseable)
- **`breach_date`**: Date when breach occurred (YYYY-MM-DD or original text)
- **`reported_date`**: Date reported to Delaware AG (YYYY-MM-DD or original text)
- **`notice_document_url`**: Direct link to PDF breach notification
- **`summary_text`**: Human-readable summary of all key details
- **`tags_keywords`**: `["delaware_ag", "de_breach", "data_breach"]`

#### Raw Data Preservation (`raw_data_json`)
```json
{
  "organization_name": "Original organization name",
  "date_of_breach": "Original breach date text",
  "reported_date": "Original reported date text", 
  "delaware_residents_affected": "Original affected count text",
  "sample_notice_link": "PDF URL"
}
```

### Data Processing Logic

#### Organization Name Extraction
- **Method**: `extract_organization_name()`
- **Handles**: Nested HTML tables, complex cell structures
- **Fallback**: Direct text extraction if nested parsing fails

#### Date Parsing
- **Method**: `parse_date_delaware()`
- **Supported Formats**:
  - `MM/DD/YYYY` (e.g., "05/28/2021")
  - `MM/DD/YY` (e.g., "05/28/21")
  - `YYYY-MM-DD` (ISO format)
  - Date ranges with en-dash (e.g., "11/19/2023 – 11/26/2023")
  - Concatenated dates (e.g., "04/09/202504/21/2025")
- **Fallback**: Preserve original text when parsing fails
- **Examples**:
  -`"Within 1 week"`stored as-is
  -`"Ransomware detected February 16, 2023"`preserved exactly

#### Affected Individuals Parsing
- **Method**: `parse_affected_individuals()`
- **Handles**: Numbers with commas (e.g., "1,023"), simple numbers, "N/A", "Unknown"
- **Returns**: Integer when parseable, None otherwise
- **Preservation**: Original text always saved in `raw_data_json`

#### Date Filtering
- **Rule**: Only collect breaches from today onward (exclude archived listings)
- **Exception**: Records with unparseable dates use current date fallback to preserve data
- **Logic**: `if successfully_parsed_date and date < today: skip`

---

## Error Handling & Data Preservation

### Philosophy: "Preserve Everything"
The scraper prioritizes data preservation over perfect parsing. When parsing fails, original information is retained.

### Specific Handling
1. **Unparseable Dates**: Use current date as `publication_date`, store original text in date fields
2. **Non-numeric Affected Counts**: Store as NULL in integer field, preserve in raw JSON
3. **Missing Organization Names**: Skip only if completely empty
4. **Complex HTML**: Extract from nested tables and structures
5. **Duplicate URLs**: Handle gracefully with unique URL generation

### Logging Levels
- **INFO**: Successful operations, data preservation fallbacks
- **WARNING**: Parsing failures (but data still preserved)
- **ERROR**: Critical failures that prevent data collection

---

## Database Schema

### Primary Table: `scraped_items`
```sql
-- Core fields
source_id: INTEGER (3 for Delaware AG)
item_url: TEXT (unique constraint)
title: TEXT (organization name)
publication_date: TIMESTAMP
scraped_at: TIMESTAMP (auto)
created_at: TIMESTAMP (auto)

-- Content fields  
summary_text: TEXT
full_content: TEXT (unused for this source)
raw_data_json: JSONB
tags_keywords: TEXT[]

-- Structured breach fields (added 2025-05-26)
affected_individuals: INTEGER
breach_date: DATE (or TEXT for unparseable)
reported_date: DATE (or TEXT for unparseable)  
notice_document_url: TEXT
```

### Indexes
- `idx_scraped_items_affected_individuals`
- `idx_scraped_items_breach_date`
- `idx_scraped_items_reported_date`

---

## Configuration

### Constants
```python
SOURCE_ID_DELAWARE_AG = 3
DELAWARE_AG_BREACH_URL = "https://attorneygeneral.delaware.gov/fraud/cpu/securitybreachnotification/database/"
```

### Dependencies
- `requests`: HTTP requests
- `beautifulsoup4`: HTML parsing
- `datetime`: Date handling
- `urllib.parse`: URL manipulation
- `re`: Regular expressions for date parsing

---

## Quality Assurance

### Data Validation
- Organization name must not be empty
- At least one date field must have content
- PDF links validated as proper URLs
- Duplicate detection by title + date + source

### Testing Approach
- Parse sample of recent entries
- Verify all date formats handle correctly
- Confirm data preservation for edge cases
- Validate database field population

### Monitoring
- Track parsing success rates
- Monitor for website structure changes
- Alert on significant data volume changes
- Log all preservation fallbacks for review

---

## Maintenance Notes

### Potential Issues
1. **Website Structure Changes**: Delaware AG may modify table layout
2. **New Date Formats**: Additional date formats may appear
3. **PDF Link Changes**: URL structure for documents may change
4. **Rate Limiting**: Site may implement request throttling

### Update Procedures
1. Monitor scraper logs for new parsing warnings
2. Test against current website structure monthly
3. Update date parsing patterns as needed
4. Verify database schema supports new data types

### Contact Information
- **Data Source**: Delaware Attorney General's Office
- **Technical Issues**: Monitor GitHub Actions logs
- **Schema Changes**: Update via Supabase migrations

---

## Sample Data Output

### Successful Parse Example
```json
{
  "title": "Bayhealth Medical Center",
  "affected_individuals": 1023,
  "breach_date": "2021-05-04",
  "reported_date": "2021-05-28", 
  "notice_document_url": "https://attorneygeneral.delaware.gov/.../notice.pdf",
  "summary_text": "Reported to Delaware AG: 5/28/2021. Breach occurred: 5/4/2021. Delaware residents affected: 1,023. Sample notice available.",
  "raw_data_json": {
    "organization_name": "Bayhealth Medical Center",
    "date_of_breach": "5/4/2021",
    "reported_date": "5/28/2021",
    "delaware_residents_affected": "1,023",
    "sample_notice_link": "https://attorneygeneral.delaware.gov/.../notice.pdf"
  }
}
```

### Data Preservation Example
```json
{
  "title": "International Center of Photography",
  "affected_individuals": null,
  "breach_date": "Ransomware detected February 16, 2023",
  "reported_date": "Within 1 week",
  "notice_document_url": "https://attorneygeneral.delaware.gov/.../notice.pdf",
  "summary_text": "Reported to Delaware AG: Within 1 week. Breach occurred: Ransomware detected February 16, 2023. Sample notice available.",
  "raw_data_json": {
    "organization_name": "International Center of Photography", 
    "date_of_breach": "Ransomware detected February 16, 2023",
    "reported_date": "Within 1 week",
    "sample_notice_link": "https://attorneygeneral.delaware.gov/.../notice.pdf"
  }
}
```
