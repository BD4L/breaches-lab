# California AG Scraper - New Architecture

## Problem Solved

The original California AG scraper was timing out in GitHub Actions due to:
- Processing 4,564+ historical records with heavy PDF analysis
- 6+ hour runtime exceeding GitHub Actions limits
- Network timeouts and connection issues
- Unreliable PDF processing blocking the entire pipeline

## Solution: Separated Concerns Architecture

### **Primary Scraper** (Fast & Reliable)
- **Purpose**: Daily breach data collection
- **Speed**: ~2 minutes
- **Reliability**: High (no timeouts)
- **Data**: Essential breach information + PDF URLs for later analysis

### **Secondary Enrichment Service** (Deep Analysis)
- **Purpose**: PDF analysis and detailed data extraction
- **Speed**: Variable (depends on PDF count)
- **Reliability**: Isolated failures don't block main collection
- **Data**: Comprehensive breach details, data types, financial impact

## Processing Modes

### **BASIC Mode** - Ultra Fast
```bash
CA_AG_PROCESSING_MODE=BASIC
```
- CSV data only
- ~30 seconds runtime
- Zero timeout risk
- No detail pages or PDFs
- **Use case**: Emergency data collection, testing

### **ENHANCED Mode** - Recommended for GitHub Actions
```bash
CA_AG_PROCESSING_MODE=ENHANCED  # Default
```
- CSV data + detail page scraping
- PDF URLs collected and stored
- ~2-5 minutes runtime
- Low timeout risk
- PDFs not analyzed (deferred)
- **Use case**: Daily automated collection

### **FULL Mode** - Complete Analysis
```bash
CA_AG_PROCESSING_MODE=FULL
```
- Everything: CSV + detail pages + PDF analysis
- Complete breach intelligence
- 30+ minutes runtime
- High timeout risk
- **Use case**: Local research, comprehensive analysis

## Usage Examples

### GitHub Actions (Automated Daily)
```yaml
env:
  CA_AG_PROCESSING_MODE: "ENHANCED"
  CA_AG_FILTER_FROM_DATE: "2025-05-21"  # One week back
```
**Result**: Collects 10 recent breaches with PDF URLs in ~2 minutes

### Local Development (Quick Test)
```bash
export CA_AG_PROCESSING_MODE=BASIC
export CA_AG_FILTER_FROM_DATE=2025-05-27
python3 scrapers/fetch_california_ag.py
```
**Result**: Fast CSV-only collection for testing

### Local Research (Full Analysis)
```bash
export CA_AG_PROCESSING_MODE=FULL
export CA_AG_FILTER_FROM_DATE=2025-05-01
python3 scrapers/fetch_california_ag.py
```
**Result**: Complete analysis including PDF processing

### PDF Enrichment Service (Separate)
```bash
# Analyze PDFs for records that have URLs but no analysis
python3 scrapers/enrich_california_pdfs.py --limit 5

# Analyze PDFs for specific organization
python3 scrapers/enrich_california_pdfs.py --org-name "ALN Medical"

# Dry run to see what would be processed
python3 scrapers/enrich_california_pdfs.py --dry-run
```

## Performance Comparison

| Mode | Records | Runtime | Timeout Risk | PDF Analysis | Use Case |
|------|---------|---------|--------------|--------------|----------|
| **BASIC** | 10 recent | 30 sec | None | None | Testing |
| **ENHANCED** | 10 recent | 2-5 min | Low | URLs only | GitHub Actions |
| **FULL** | 10 recent | 10-30 min | Medium | Complete | Local research |
| **FULL** | All historical | 6+ hours | High | Complete | One-time analysis |

## Workflow

### Daily Automated Collection (GitHub Actions)
1. **ENHANCED mode** collects recent breaches with PDF URLs
2. Data stored in database with `pdf_analyzed: false`
3. Essential breach information immediately available

### Weekly PDF Enrichment (Manual/Scheduled)
1. **PDF enrichment service** finds records with unanalyzed PDFs
2. Downloads and analyzes PDFs separately
3. Updates records with detailed analysis
4. No impact on daily collection if it fails

## Data Structure

### Enhanced Mode Output
```json
{
  "organization_name": "ALN Medical Management, LLC",
  "breach_dates": ["2024-03-18", "2024-03-24"],
  "tier_2_detail": {
    "detail_page_scraped": true,
    "pdf_links": [
      {
        "url": "https://oag.ca.gov/system/files/...",
        "title": "Sample Notification"
      }
    ]
  },
  "tier_3_pdf_analysis": [
    {
      "pdf_analyzed": false,
      "skip_reason": "ENHANCED mode - PDF analysis deferred",
      "pdf_url": "https://oag.ca.gov/system/files/...",
      "pdf_title": "Sample Notification"
    }
  ]
}
```

### After PDF Enrichment
```json
{
  "tier_3_pdf_analysis": [
    {
      "pdf_analyzed": true,
      "data_types_compromised": ["SSN", "Medical Records"],
      "affected_individuals": 1500,
      "financial_impact": "Unknown",
      "analysis_timestamp": "2025-05-27T21:45:00"
    }
  ]
}
```

## Benefits

### Reliability
- Main scraper never times out
- PDF failures don't block daily collection
- Consistent data availability

### Flexibility
- Choose processing depth based on needs
- Run PDF analysis when convenient
- Scale analysis independently

### Efficiency
- Fast daily collection (2 minutes vs 6+ hours)
- Resource-intensive analysis runs separately
- Better GitHub Actions utilization

### Maintainability
- Clear separation of concerns
- Easier debugging and testing
- Independent service scaling

## Configuration Reference

### Environment Variables
```bash
# Processing mode
CA_AG_PROCESSING_MODE=ENHANCED  # BASIC, ENHANCED, FULL

# Date filtering
CA_AG_FILTER_FROM_DATE=2025-05-21  # YYYY-MM-DD or empty for all

# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key
```

### GitHub Actions Settings
```yaml
env:
  CA_AG_PROCESSING_MODE: "ENHANCED"     # Recommended
  CA_AG_FILTER_FROM_DATE: "2025-05-21" # One week back for testing
```

This architecture ensures reliable daily breach monitoring while preserving the ability to perform deep analysis when needed.
