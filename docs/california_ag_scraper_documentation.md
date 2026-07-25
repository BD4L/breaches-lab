# California AG Enhanced Scraper Documentation

## Overview

The California Attorney General's Office enhanced scraper implements a **3-tier data collection approach** using the CSV export endpoint for reliable and comprehensive breach data collection. This implementation represents a significant upgrade from the previous HTML-based scraper.

## Implementation Status

- **Status**: EXCELLENT
- **Implementation Date**: May 27, 2025
- **Data Source**: California AG Data Breach Notification Portal
- **Primary URL**: https://oag.ca.gov/privacy/databreach/list
- **CSV Endpoint**: https://oag.ca.gov/privacy/databreach/list-export

## Architecture

### 3-Tier Data Collection Approach

#### **Tier 1: Portal Raw Data (CSV-based)**
- **Source**: CSV export endpoint (`/privacy/databreach/list-export`)
- **Method**: Direct CSV download and parsing
- **Advantages**:
  - Reliable data structure
  - Complete dataset access
  - No HTML parsing complexity
  - Resistant to website layout changes

#### **Tier 2: Derived/Enriched Data**
- **Enhancement**: Incident UID generation for deduplication
- **Processing**: Date standardization and validation
- **Filtering**: Recent breaches only (today onward)
- **Structure**: Standardized field mapping

#### **Tier 3: Deep Analysis (PDF Processing)**
- **PDF Download**: Retrieves breach notification documents
- **Content Extraction**: Analyzes PDF text for breach details
- **Affected Individuals**: Extracts count using regex patterns
- **Data Classification**: Identifies compromised data types (SSN, driver license, etc.)
- **Contact Information**: Captures breach response contacts

## Data Structure

### CSV Source Fields
```csv
"Organization Name","Date(s) of Breach (if known)","Reported Date"
```

### Enhanced Database Fields
- `source_id`: 4 (California AG)
- `item_url`: Detail page URL (from hyperlink following)
- `title`: Organization name
- `publication_date`: Reported date (YYYY-MM-DD)
- `summary_text`: Enhanced summary with data types and affected count
- `full_content`: Comprehensive breach details with PDF analysis
- `reported_date`: Standardized reported date
- `breach_date`: First breach date (if available)
- `affected_individuals`: Count extracted from PDF analysis
- `notice_document_url`: Direct link to PDF notification
- `data_types_compromised`: Array of compromised data types
- `raw_data_json`: Complete 3-tier data structure

### Raw Data JSON Structure
```json
{
  "scraper_version": "3.0_enhanced_with_pdfs",
  "tier_1_csv_data": {
    "Organization Name": "Mission Bell Mfg Inc",
    "Date(s) of Breach (if known)": "01/31/2025",
    "Reported Date": "04/04/2025"
  },
  "tier_2_enhanced": {
    "incident_uid": "ca_ag_mission_bell_mfg_inc_2025-04-04",
    "breach_dates_all": ["2025-01-31"],
    "enhancement_attempted": true,
    "enhancement_timestamp": "2025-05-27T...",
    "detail_page_data": {
      "detail_page_scraped": true,
      "detail_page_url": "https://oag.ca.gov/ecrime/databreach/reports/sb24-600915",
      "pdf_links": [
        {
          "url": "https://oag.ca.gov/system/files/Data%20Security%20Letter%20Final.pdf",
          "title": "Data Security Letter"
        }
      ]
    }
  },
  "tier_3_pdf_analysis": [
    {
      "pdf_analyzed": true,
      "pdf_url": "https://oag.ca.gov/system/files/Data%20Security%20Letter%20Final.pdf",
      "affected_individuals": null,
      "data_types_compromised": ["Social Security Numbers", "Driver License Numbers"],
      "incident_details": "Security breach discovered on February 1st, occurred on January 31st"
    }
  ]
}
```

## Technical Implementation

### Key Functions

#### `fetch_csv_data()`
- Downloads CSV data from the export endpoint
- Parses CSV into structured records
- Generates incident UIDs for deduplication
- Handles date parsing for multiple formats

#### `parse_date_flexible(date_str)`
- Supports MM/DD/YYYY format from CSV
- Handles multiple dates (comma-separated)
- Returns standardized YYYY-MM-DD format
- Graceful handling of "n/a" and empty values

#### `parse_breach_dates(date_str)`
- Extracts multiple breach dates from single field
- Returns list of standardized dates
- Handles various date formats and separators

#### `scrape_detail_page(detail_url)`
- Scrapes individual breach detail pages
- Extracts organization name and breach dates
- Finds PDF notification document links
- Returns structured detail page data

#### `analyze_pdf_content(pdf_url)`
- Downloads and analyzes PDF notification documents
- Extracts affected individuals count using regex patterns
- Identifies data types compromised (SSN, driver license, etc.)
- Returns comprehensive PDF analysis data

#### `generate_incident_uid(org_name, reported_date)`
- Creates unique identifier for deduplication
- Format: MD5 hash of "ca_ag_{org}_{date}"
- Ensures consistent UIDs across runs

### Date Filtering (Configurable)
- **Testing Mode**:`CA_AG_FILTER_FROM_DATE`not set Collect ALL historical data
- **Production Mode**:`CA_AG_FILTER_FROM_DATE="2025-05-27"`Filter from specified date
- **Purpose**: Flexible data collection for testing vs production
- **Fallback**: Include records with unparseable dates

## Performance Characteristics

### Advantages
- **Reliability**: CSV endpoint is stable and structured
- **Completeness**: Access to full dataset (1000+ records)
- **Speed**: Single HTTP request for all data
- **Maintenance**: Minimal maintenance required

### Data Quality
- **Coverage**: Comprehensive breach notifications
- **Accuracy**: Direct from official source
- **Timeliness**: Real-time updates from AG office
- **Standardization**: Consistent field mapping

## Sample Data

### Recent Breach Examples
```
Organization: ALN Medical Management, LLC
Breach Date(s): 03/18/2024, 03/24/2024
Reported Date: 05/23/2025

Organization: Blue Shield of California
Breach Date(s): 04/01/2021
Reported Date: 04/09/2025
```

### Data Volume
- **Total Records**: 1000+ breach notifications
- **Date Range**: 2015-2025 (historical data available)
- **Recent Activity**: 5-10 new breaches per day

## Usage

### Manual Execution

#### Testing Mode (All Historical Data)
```bash
cd /path/to/Breaches
# No date filter - collects all historical data
python3 scrapers/fetch_california_ag.py
```

#### Production Mode (Date Filtered)
```bash
cd /path/to/Breaches
# Filter from specific date onward
export CA_AG_FILTER_FROM_DATE="2025-05-27"
python3 scrapers/fetch_california_ag.py
```

### GitHub Actions Integration
- **Workflow**: `.github/workflows/main_scraper_workflow.yml`
- **Schedule**: Daily at 3 AM UTC
- **Command**: `python scrapers/fetch_california_ag.py`

## Configuration

### Environment Variables
- `SUPABASE_URL`: Database connection URL
- `SUPABASE_SERVICE_KEY`: Database service key
- `CA_AG_FILTER_FROM_DATE`: Optional date filter (YYYY-MM-DD format)
  - **Not set**: Collect all historical data (testing mode)
  - **Set**: Filter breaches from specified date onward (production mode)

### Constants
```python
CALIFORNIA_AG_BREACH_URL = "https://oag.ca.gov/privacy/databreach/list"
CALIFORNIA_AG_CSV_URL = "https://oag.ca.gov/privacy/databreach/list-export"
SOURCE_ID_CALIFORNIA_AG = 4
```

## Troubleshooting

### Common Issues

#### CSV Endpoint Unavailable
- **Symptom**: HTTP errors when accessing CSV URL
- **Solution**: Verify endpoint availability, check headers
- **Fallback**: Could implement HTML table parsing

#### Date Parsing Failures
- **Symptom**: Dates not parsing correctly
- **Solution**: Check date format in CSV, update parsing logic
- **Current Format**: MM/DD/YYYY

#### Duplicate Records
- **Symptom**: Same breach appearing multiple times
- **Solution**: Verify incident UID generation logic
- **Deduplication**: Based on organization + reported date

## Monitoring

### Success Metrics
- **Records Processed**: Track daily collection volume
- **Date Coverage**: Ensure recent breaches are captured
- **Error Rate**: Monitor parsing and insertion failures

### Logging
- **Level**: INFO for normal operations, ERROR for failures
- **Format**: Timestamp, level, message
- **Key Events**: CSV fetch, record processing, database insertion

## Future Enhancements

### Tier 3 Implementation
1. **PDF Analysis**: Extract detailed breach information
2. **Affected Individuals**: Parse notification documents
3. **Data Classification**: Identify compromised data types
4. **Cost Analysis**: Extract financial impact information

### Additional Features
1. **Historical Analysis**: Trend analysis capabilities
2. **Enhanced Deduplication**: Cross-reference with other sources
3. **Real-time Monitoring**: Webhook notifications for new breaches

## Related Documentation

- [Implementation Status](../SCRAPER_IMPLEMENTATION_STATUS.md)
- [Database Schema](../database_schema.sql)
- [Delaware AG Implementation](./delaware_ag_scraper_documentation.md)
- [Standardized Field Mapping](./standardized_field_mapping.md)

---

**Last Updated**: May 27, 2025
**Version**: 2.0 Enhanced
**Maintainer**: Breach Monitoring System
