# Enhanced Indiana AG Scraper Implementation

## Overview
The Indiana Attorney General's Office maintains yearly PDF reports containing tabular data of all data breach notifications reported to the state. This enhanced scraper processes these yearly reports to extract individual breach records with comprehensive field mapping.

**Status**: EXCELLENT
**Last Updated**: 2025-01-28
**Implementation**: 3-tier data structure with PDF table parsing

## Data Source Details

### Primary URL
- **Main Page**: `https://www.in.gov/attorneygeneral/2874.htm`
- **Data Format**: Yearly PDF reports (2014-2025)
- **Update Frequency**: Ongoing (new breaches added to current year PDF)

### Data Structure
The Indiana AG portal provides:
- Links to yearly PDF reports containing all breaches for that year
- Each PDF contains tabular data with columns for:
  - Row Number (skipped)
  - Organization Name
  - Date Reported to AG
  - Date of Breach
  - Number of Indiana Residents Affected
- **Important**: The affected individuals count represents **Indiana residents only**, not total affected individuals across all states
- **Note**: PDF does not contain "Information Compromised" details or total affected individuals

## Implementation Architecture

### 3-Tier Data Structure

#### Tier 1: Portal Data (Raw PDF Extraction)
```json
{
  "tier_1_portal_data": {
    "pdf_url": "https://www.in.gov/.../DB-YeartoDate-Report-May2025.pdf",
    "pdf_year": "2025",
    "extraction_timestamp": "2025-01-28T10:30:00Z",
    "page_number": 2,
    "row_index": 5,
    "raw_organization_name": "Example Corp",
    "raw_breach_date": "01/15/2025",
    "raw_reported_date": "01/20/2025",
    "raw_affected_individuals": "1,234",
    "raw_information_compromised": "SSN, DOB, Address",
    "processing_mode": "ENHANCED"
  }
}
```

#### Tier 2: Derived/Enrichment (Computed Fields)
```json
{
  "tier_2_derived_data": {
    "incident_uid": "IN-AG-2025-005",
    "portal_first_seen_utc": "2025-01-28T10:30:00Z",
    "portal_last_seen_utc": "2025-01-28T10:30:00Z",
    "breach_record_index": 5,
    "data_types_normalized": ["Social Security Numbers", "Personal Information"],
    "affected_individuals_parsed": 1234,
    "breach_date_parsed": "2025-01-15T00:00:00Z",
    "reported_date_parsed": "2025-01-20T00:00:00Z",
    "extraction_confidence": "high"
  }
}
```

#### Tier 3: Deep Analysis (Enhanced Processing)
```json
{
  "tier_3_deep_analysis": {
    "data_types_detailed": ["Social Security Numbers", "Personal Information"],
    "incident_timeline": {
      "breach_date": "2025-01-15T00:00:00Z",
      "reported_date": "2025-01-20T00:00:00Z"
    },
    "regulatory_context": {
      "state": "Indiana",
      "reporting_authority": "Indiana Attorney General",
      "disclosure_law": "Indiana Data Breach Notification Law"
    },
    "analysis_timestamp": "2025-01-28T10:30:00Z"
  }
}
```

## Key Features

### PDF Table Parsing
- **Primary Method**: pdfplumber for accurate table extraction
- **Fallback Method**: PyPDF2 for text-based parsing
- **Table Detection**: Automatic identification of breach data tables
- **Header Recognition**: Skips header rows automatically

### Data Processing
- **Affected Individuals**: Parses numbers with commas, handles approximations
- **Date Parsing**: Flexible date format handling with dateutil
- **Data Types**: Normalizes to standardized categories
- **Organization Names**: Cleans and validates entity names

### Processing Scope
- **Current Implementation**: Process only 2025 data for current breach monitoring
- **Rationale**: Focus on most recent breaches for dashboard efficiency
- **Available Data**: 2025 year-to-date report (updated regularly by Indiana AG)

### Date Filtering
- Environment variable: `IN_AG_FILTER_FROM_DATE` (YYYY-MM-DD format)
- Filters based on breach date or reported date
- GitHub Actions default: One week back for testing

## Data Limitations and Scope

### Important Considerations
- **Affected Individuals Scope**: The `affected_individuals` field contains **Indiana residents only**, not total affected individuals across all states
- **Geographic Limitation**: For multi-state breaches, this represents only the Indiana impact
- **Comparison Caution**: When comparing with other state AG portals, note that each shows only their state's residents
- **Total Impact Unknown**: The actual total affected individuals across all states is not available in this dataset

### Use Cases
- **Indiana-specific impact analysis**: Accurate for understanding breach impact on Indiana residents
- **State compliance tracking**: Shows which organizations reported to Indiana AG
- **Regional breach patterns**: Good for Indiana-focused breach monitoring
- **Cross-state analysis**: Requires combining with other state AG data for complete picture

## Database Field Mapping

### Core Fields
-`title`Organization Name
-`publication_date`Reported Date (or Breach Date if no reported date)
-`summary_text`Generated summary with key details

### Standardized Breach Fields
-`affected_individuals`**Indiana residents affected only** (not total affected across all states)
-`breach_date`Date of breach occurrence
-`reported_date`Date reported to Indiana AG
-`notice_document_url`URL of yearly PDF report

### Enhanced Fields
-`data_types_compromised`Normalized array of data types
-`what_was_leaked`Raw information compromised text
-`keywords_detected`Data types + standard keywords
-`tags_keywords`Enhanced tags including breach type indicators

## Unique Identifier Generation

### Incident UID Pattern
- Format: `IN-AG-{year}-{index:03d}`
- Example: `IN-AG-2025-001`, `IN-AG-2025-002`

### Item URL Pattern
- Format: `{base_url}#{year}-breach-{index:03d}`
- Example: `https://www.in.gov/attorneygeneral/2874.htm#2025-breach-001`

## Error Handling

### PDF Processing Failures
- Graceful fallback from pdfplumber to PyPDF2
- Logs extraction confidence levels
- Preserves partial data when possible

### Data Validation
- Validates essential fields (organization name, dates)
- Skips records with insufficient data
- Logs all processing decisions

### Rate Limiting
- 2-second delay between PDF requests
- Prevents server overload during bulk processing

## Configuration

### Environment Variables
```bash
IN_AG_FILTER_FROM_DATE="2025-01-20"  # Date filtering
IN_AG_PROCESSING_MODE="ENHANCED"     # Processing mode
```

### GitHub Actions Configuration
```yaml
IN_AG_FILTER_FROM_DATE: "2025-01-20"
IN_AG_PROCESSING_MODE: "ENHANCED"
```

## Performance Considerations

### GitHub Actions Optimization
- Focuses on recent years by default
- Uses ENHANCED mode for balance of completeness and speed
- Implements proper error handling to prevent workflow failures

### Memory Management
- Processes PDFs one at a time
- Clears PDF objects after processing
- Uses streaming for large PDF files

## Testing and Validation

### Data Quality Checks
- Validates organization names are not empty
- Ensures at least one date field is present
- Checks for reasonable affected individual counts

### Duplicate Prevention
- Uses unique URLs for each breach record
- Checks existing records before insertion
- Implements incident UID for deduplication

## Future Enhancements

### Potential Improvements
1. **Individual PDF Analysis**: Extract more detailed information from linked individual notices
2. **Historical Trend Analysis**: Track changes in breach patterns over time
3. **Cross-Reference Validation**: Compare with other state AG portals for same organizations
4. **Enhanced Data Types**: More granular classification of compromised information

### Monitoring
- Track PDF parsing success rates
- Monitor data quality metrics
- Alert on significant changes in data structure

## Implementation Notes

### Key Differences from Previous Version
- **Complete Rewrite**: Changed from individual PDF link processing to yearly report processing
- **Enhanced Architecture**: Implemented full 3-tier data structure
- **Improved Parsing**: Uses pdfplumber for better table extraction
- **Comprehensive Mapping**: Maps to all relevant database fields
- **Better Error Handling**: Graceful degradation and detailed logging

### Lessons Learned
- PDF table parsing requires robust fallback mechanisms
- Yearly reports provide more comprehensive data than individual notices
- Standardized data type mapping improves cross-portal analysis
- Date filtering is essential for GitHub Actions performance
