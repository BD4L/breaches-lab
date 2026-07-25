# Enhanced Iowa AG Scraper Implementation

## Overview
The Enhanced Iowa AG scraper processes security breach notifications from the Iowa Attorney General's 2025 page specifically. It implements a comprehensive 3-tier data structure with PDF analysis capabilities.

**Status**: EXCELLENT
**Last Updated**: 2025-05-29  
**Source URL**: https://www.iowaattorneygeneral.gov/for-consumers/security-breach-notifications/2025-security-breach-notification/

## Key Features

### Enhanced Implementation
- **3-tier data structure** (Portal Derived Deep Analysis)
- **2025-focused processing** for current breach monitoring
- **Comprehensive PDF analysis** with PyPDF2 and pdfplumber fallback
- **Multiple document support** (primary + supplemental documents)
- **Incident UID generation** for deduplication
- **Date filtering** (configurable via environment variables)
- **Processing modes** (BASIC, ENHANCED, FULL)

### Data Extraction
- **Date Reported**: When breach was reported to Iowa AG
- **Organization Name**: Clean company/entity names
- **PDF Documents**: Primary breach notifications + supplemental letters
- **Affected Individuals**: Extracted from PDF content
- **What Information Involved**: Extracted from breach notification text

### Architecture

#### Tier 1: Portal Data (Raw Extraction)
```json
{
  "source_url": "https://www.iowaattorneygeneral.gov/...",
  "extraction_timestamp": "2025-05-29T...",
  "table_row_index": 0,
  "raw_date_reported": "1-7-2025",
  "raw_organization_name": "Medusind, Inc. - Aspen Dental",
  "primary_pdf_url": "https://www.iowaattorneygeneral.gov/media/cms/...",
  "all_pdf_links": [...],
  "supplemental_links": [...],
  "processing_mode": "ENHANCED"
}
```

#### Tier 2: Derived/Enrichment
```json
{
  "incident_uid": "IA_AG_2025_A612FF93",
  "portal_first_seen_utc": "2025-05-29T...",
  "has_supplemental_documents": true,
  "total_documents": 2,
  "enhancement_attempted": true,
  "enhancement_errors": []
}
```

#### Tier 3: PDF Analysis
```json
{
  "pdf_analyzed": true,
  "pdf_url": "https://www.iowaattorneygeneral.gov/media/cms/...",
  "affected_individuals": 1500,
  "what_information_involved": {
    "text": "Social Security numbers, driver's license numbers..."
  },
  "extraction_confidence": "high"
}
```

## Configuration

### Environment Variables
- `IA_AG_FILTER_FROM_DATE`: Date filtering (format: "YYYY-MM-DD")
- `IA_AG_PROCESSING_MODE`: Processing mode (BASIC, ENHANCED, FULL)

### GitHub Actions Configuration
```yaml
# Iowa AG scraper configuration for GitHub Actions
IA_AG_FILTER_FROM_DATE: "2025-01-20" # One week back for reliable testing
IA_AG_PROCESSING_MODE: "ENHANCED" # Process 2025 page with comprehensive field mapping and PDF analysis
```

## Database Schema Mapping

### Standardized Fields
- `source_id`: 8 (Iowa AG)
- `item_url`: Unique URL with incident UID
- `title`: Organization name
- `publication_date`: Date reported (ISO format)
- `reported_date`: Date reported (date only)
- `affected_individuals`: Number of people affected
- `notice_document_url`: Primary PDF URL
- `what_was_leaked`: Extracted information or PDF URL fallback

### Enhanced Fields
- `summary_text`: Comprehensive breach summary
- `full_content`: Structured breach details
- `tags_keywords`: ["iowa_ag", "ia_breach", "2025"]
- `raw_data_json`: Complete 3-tier data structure

## Processing Logic

### 1. Table Parsing
- Extracts two-column table (Date Reported | Organization Name)
- Handles multiple PDF links per organization
- Detects supplemental documents automatically

### 2. Data Cleaning
- Removes supplemental text from organization names
- Extracts clean company names before commas
- Validates essential data (name, date, PDF URL)

### 3. Date Filtering
- Configurable date filtering for recent breaches
- Supports both testing (all data) and production (filtered) modes

### 4. PDF Analysis
- Downloads and analyzes breach notification PDFs
- Extracts affected individuals using regex patterns
- Extracts "what information was involved" sections
- Handles both PyPDF2 and pdfplumber for maximum compatibility

### 5. Deduplication
- Generates unique incident UIDs using organization name and date
- Checks for existing records before insertion
- Prevents duplicate entries

## Error Handling

### Robust Error Management
- PDF download timeouts and failures
- Text extraction errors with fallbacks
- Database insertion error logging
- Comprehensive exception handling with context

### Fallback Strategies
- PyPDF2 pdfplumber for PDF extraction
- PDF URL fallback for "what was leaked" field
- Graceful handling of missing data

## Performance Optimizations

### GitHub Actions Optimized
- Rate limiting between requests (2-second delays)
- Efficient table parsing
- Minimal memory footprint
- Timeout handling for automated workflows

### Processing Modes
- **BASIC**: Table data only, no PDF analysis
- **ENHANCED**: Table data + PDF analysis
- **FULL**: Complete analysis with all features

## Testing

### Validation Points
- Date parsing accuracy (M-D-YYYY format)
- PDF link extraction completeness
- Supplemental document detection
- Database field mapping correctness

### Sample Data
- 30+ breach notifications in 2025
- Multiple document types per breach
- Various organization name formats
- Supplemental letters with dates

## Maintenance

### Regular Updates
- Monitor Iowa AG page structure changes
- Update PDF extraction patterns as needed
- Adjust date filtering for production use
- Review and update documentation

### Monitoring
- Track processing success rates
- Monitor PDF extraction confidence levels
- Review enhancement error logs
- Validate data quality in dashboard

---

**Implementation Status**: Complete and Production Ready
**Next Steps**: Monitor performance in GitHub Actions and adjust configurations as needed
