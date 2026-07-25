# Enhanced Delaware AG Scraper Implementation Guide

## Overview

This document outlines the enhanced Delaware AG scraper implementation that follows your proposed three-tier data structure:

- **A. Raw extraction** (direct from HTML table)
- **B. Derived/enrichment** (computed fields)  
- **C. Deep-dive from PDF** (future implementation)

## Data Structure

### Current Enhanced raw_data_json Structure

```json
{
  "delaware_ag_raw": {
    "org_name": "Company Name",
    "breach_date_raw": "04/15/2025",
    "reported_date_raw": "04/20/2025", 
    "de_residents_affected_raw": "1,250",
    "sample_notice_url": "https://...",
    "row_notes": "Supplemental",
    "listing_year": 2025
  },
  "delaware_ag_derived": {
    "incident_uid": "abc123def456",
    "portal_first_seen_utc": "2025-01-26T...",
    "portal_last_seen_utc": "2025-01-26T...",
    "is_supplemental": true,
    "breach_duration_days": null,
    "seen_multiple_report_dates": false
  },
  "delaware_ag_pdf_analysis": {
    "pdf_processed": false,
    "incident_description": null,
    "data_types_compromised": [],
    "date_discovered": null,
    "date_contained": null,
    "credit_monitoring_offered": null,
    "monitoring_duration_months": null,
    "consumer_callcenter_phone": null,
    "regulator_contact": null,
    "pdf_text_blob": null
  }
}
```

## Field Mapping to Existing Schema

| Dashboard Field | Source | Existing Schema Field |
|----------------|--------|---------------------|
| **Org Name** | HTML table | `title` |
| **Date of Breach** | HTML table | `breach_date` + `raw_data_json.delaware_ag_raw.breach_date_raw` |
| **Reported Date** | HTML table | `reported_date` + `raw_data_json.delaware_ag_raw.reported_date_raw` |
| **Number Affected** | HTML table | `affected_individuals` + `raw_data_json.delaware_ag_raw.de_residents_affected_raw` |
| **Origin (hyperlink)** | HTML table | `notice_document_url` + `exhibit_urls` |
| **Documents** | PDF analysis | `exhibit_urls` + `raw_data_json.delaware_ag_pdf_analysis` |

## Enhanced Functions Added

### 1. `extract_organization_name(cell) -> tuple[str, str]`
- Extracts org name AND row notes (like "Supplemental", "Addendum")
- Handles complex HTML structures
- Returns: `(org_name, row_notes)`

### 2. `generate_incident_uid(org_name: str, breach_date: str) -> str`
- Creates unique incident identifier
- Uses MD5 hash of org_name + breach_date
- Enables deduplication and tracking

### 3. `check_multiple_dates(date_str: str) -> bool`
- Detects multiple report dates
- Looks for keywords like "substitute", "media", "various"
- Counts date patterns in string

### 4. `analyze_pdf_notice(pdf_url: str) -> dict` (Placeholder)
- Future PDF analysis implementation
- Will extract detailed breach information
- Uses pdfminer or Apache Tika

## Implementation Benefits

### **Immediate Improvements**
1. **Enhanced data capture** - Row notes, multiple date detection
2. **Better organization** - Structured raw_data_json with clear sections
3. **Unique identifiers** - incident_uid for deduplication
4. **Supplemental tracking** - Flags for addendum/supplemental notices

### **Leverages Existing Schema**
1. **No schema changes required** - Uses existing fields optimally
2. **Backward compatible** - Existing data remains intact
3. **Indexed fields** - Key data in dedicated columns for fast queries
4. **Flexible storage** - Raw JSON for future enhancements

### **Future-Ready**
1. **PDF analysis framework** - Ready for implementation
2. **Extensible structure** - Easy to add new fields
3. **Dashboard-ready** - All fields mapped for UI display
4. **Cross-portal consistency** - Follows standardized approach

## Next Steps

### Phase 1: Test Enhanced Scraper (Completed)
- [x] Enhanced raw_data_json structure
- [x] Improved organization name extraction
- [x] Row notes detection
- [x] Multiple date detection
- [x] Incident UID generation

### Phase 2: Dashboard Integration
- [ ] Update dashboard to display new fields
- [ ] Add filtering by supplemental notices
- [ ] Show incident UIDs for deduplication
- [ ] Display row notes and multiple date flags

### Phase 3: PDF Analysis Implementation
- [ ] Install pdfminer or Apache Tika
- [ ] Implement `analyze_pdf_notice()` function
- [ ] Extract incident descriptions
- [ ] Parse data types compromised
- [ ] Extract contact information
- [ ] Store full PDF text for re-analysis

### Phase 4: Cross-Portal Standardization
- [ ] Apply similar enhancements to other AG scrapers
- [ ] Standardize raw_data_json structure across portals
- [ ] Implement unified incident UID system
- [ ] Create cross-portal deduplication logic

## Dashboard Fields Ready for Implementation

Your proposed dashboard fields are now fully supported:

1. **org_name**`title`field
2. **breach_date_raw**`raw_data_json.delaware_ag_raw.breach_date_raw`+`breach_date`
3. **reported_date_raw**`raw_data_json.delaware_ag_raw.reported_date_raw`+`reported_date`
4. **de_residents_affected**`affected_individuals`+`raw_data_json.delaware_ag_raw.de_residents_affected_raw`
5. **sample_notice_url**`notice_document_url`+`exhibit_urls`
6. **row_notes**`raw_data_json.delaware_ag_raw.row_notes`
7. **incident_uid**`raw_data_json.delaware_ag_derived.incident_uid`
8. **is_supplemental**`raw_data_json.delaware_ag_derived.is_supplemental`

The enhanced scraper now captures all the granular data you requested while maintaining compatibility with your existing schema and providing a clear path for future PDF analysis implementation.
