# Montana AG Scraper Documentation

**Enhanced Montana AG Security Breach Notification Scraper**  
**URL**: https://dojmt.gov/office-of-consumer-protection/reported-data-breaches/  
**Source ID**: 12  
**Last Updated**: January 28, 2025

## Overview

The Montana AG scraper has been completely rewritten to follow the California AG approach with comprehensive PDF analysis and enhanced database field mapping. It processes breach notifications from the Montana Department of Justice Office of Consumer Protection.

## Website Structure Analysis

### **Current Website Format (2025)**
- **URL**: https://dojmt.gov/office-of-consumer-protection/reported-data-breaches/
- **Format**: Paginated table with comprehensive breach data
- **Pagination**: Multiple pages with navigation controls

### **Table Structure (6 Columns)**
| Column | Field | Database Mapping |
|--------|-------|------------------|
| Business Name | Organization name | `title` |
| Notification Documents | PDF link | `notice_document_url` |
| Start of Breach | Incident start date | `breach_date` (combined) |
| End of Breach | Incident end date | `breach_date` (combined) |
| Date Reported | Reported to AG | `reported_date` |
| Montanans Affected | Number affected | `affected_individuals` |

## PDF Analysis Approach

### **Following California AG Method**
The scraper extracts detailed information from breach notification PDFs:

1. **"What Information Was Involved?" Section**
   - Extracts complete text from this section
   - Saves to `what_was_leaked` field
   - Identifies specific data types compromised

2. **"What Happened?" Section**
   - Extracts incident description
   - Saves to incident analysis fields

3. **Data Type Detection**
   - Social Security Numbers
   - Driver's Licenses
   - Financial Account Information
   - Medical Records
   - Personal Information (names, addresses, etc.)

### **PDF Processing Libraries**
- **Primary**: PyPDF2 for text extraction
- **Fallback**: pdfplumber for complex PDFs
- **Error Handling**: Graceful degradation with URL fallback

## Database Schema Utilization

### **Standardized Breach Fields**
```sql
affected_individuals INTEGER,     -- Montana residents affected
breach_date TEXT,                -- Combined start/end dates
reported_date DATE,              -- When reported to AG
notice_document_url TEXT,        -- PDF link
what_was_leaked TEXT,           -- Extracted from PDF
file_size_bytes INTEGER,        -- PDF metadata
data_types_compromised TEXT[]   -- Structured data types
```

### **Three-Tier Data Structure**
```json
{
  "montana_ag_raw": {
    "business_name": "Company Name",
    "start_of_breach": "01/10/2025",
    "end_of_breach": "02/27/2025",
    "date_reported": "05/31/2025",
    "montanans_affected": "18",
    "notification_documents": "PDF_URL"
  },
  "montana_ag_derived": {
    "incident_uid": "mt_ag_12345678",
    "breach_date_combined": "01/10/2025 to 02/27/2025",
    "pdf_processed": true
  },
  "montana_ag_pdf_analysis": {
    "what_information_involved_text": "name, drivers' license, and Social Security number",
    "data_types_compromised": ["Social Security Number", "Driver's License", "Name"],
    "file_size_bytes": 245760,
    "extraction_confidence": "high"
  }
}
```

## Configuration Options

### **Environment Variables**
- `MT_AG_FILTER_FROM_DATE`: Date filter (default: "2025-01-01")
- `MT_AG_PROCESSING_MODE`: BASIC, ENHANCED, FULL (default: "ENHANCED")
- `MT_AG_MAX_PAGES`: Page limit for GitHub Actions (default: 5)

### **Processing Modes**
1. **BASIC**: Table data only, no PDF analysis
2. **ENHANCED**: Table data + PDF text extraction
3. **FULL**: Complete analysis with all PDF features

## Key Features

### **Enhanced Data Extraction**
- **Business name normalization**
- **Date range combination** (start to end breach dates)
- **PDF content analysis** following CA AG approach
- **Affected individuals parsing**
- **Data type classification**
- **Incident UID generation**

### **Rate Limiting & Error Handling**
- **2-second delays** between requests
- **Graceful PDF parsing failures**
- **Date filter application**
- **Pagination support**
- **Comprehensive logging**

### **Database Integration**
- **Standardized schema fields**
- **Three-tier raw data structure**
- **Duplicate prevention** via unique URLs
- **Error recovery** with fallback values

## Sample Data Output

### **Extracted Record Example**
```json
{
  "title": "Scheveck & Salminen",
  "affected_individuals": 18,
  "breach_date": "01/10/2025 to 02/27/2025",
  "reported_date": "2025-05-31",
  "what_was_leaked": "name, drivers' license, and Social Security number",
  "notice_document_url": "https://dojmt.gov/wp-content/uploads/2025/05/Consumer-notification-letter-7.pdf",
  "data_types_compromised": ["Social Security Number", "Driver's License", "Name"],
  "file_size_bytes": 245760
}
```

## Performance Metrics

### **Expected Performance**
- **Processing Speed**: ~2-3 seconds per breach (with PDF)
- **Success Rate**: >95% for table data, >80% for PDF extraction
- **GitHub Actions Time**: ~3-5 minutes for 3 pages
- **Memory Usage**: Moderate (PDF processing)

### **Error Handling**
- **PDF Download Failures**: Fallback to PDF URL
- **Text Extraction Failures**: Graceful degradation
- **Date Parsing Issues**: Flexible parsing with fallbacks
- **Network Issues**: Retry logic with rate limiting

## Comparison with Previous Version

| Feature | Old Scraper | Enhanced Scraper |
|---------|-------------|------------------|
| **URL** | Old structure | Current website |
| **PDF Analysis** | None | Full extraction |
| **Database Fields** | Basic only | 44+ fields |
| **Date Handling** | Limited | Comprehensive |
| **Error Recovery** | Basic | Advanced |
| **Data Quality** | Low | High |

## Integration Status

### **Workflow Integration**
- **Parallel execution** in State AG Group 3
- **Environment configuration** in GitHub Actions
- **Error isolation** from other scrapers
- **Comprehensive reporting**

### **Dashboard Compatibility**
- **Standardized fields** for cross-portal analysis
- **Rich metadata** for detailed breach intelligence
- **PDF links** for source verification
- **Data type arrays** for filtering and analysis

---

**Status**: Production Ready
**Next Review**: February 2025  
**Maintainer**: Breach Data Aggregation Team
