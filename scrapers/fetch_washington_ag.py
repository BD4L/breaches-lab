import os
import logging
import requests
import hashlib
import time
import random
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from urllib.parse import urljoin
from dateutil import parser as dateutil_parser # For flexible date parsing

# Assuming SupabaseClient is in utils.supabase_client
try:
    from utils.supabase_client import SupabaseClient
except ImportError:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from utils.supabase_client import SupabaseClient

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
WASHINGTON_AG_BREACH_URL = "https://www.atg.wa.gov/data-breach-notifications"
SOURCE_ID_WASHINGTON_AG = 5

# Configuration for date filtering
# Set to None to collect all historical data (for testing)
# Set to a date string like "2025-01-27" for production filtering
# Default to beginning of current month for comprehensive coverage in GitHub Actions
default_date = "2025-06-01"
FILTER_FROM_DATE = os.environ.get("WA_AG_FILTER_FROM_DATE", default_date)

# Rate limiting configuration
MIN_DELAY_SECONDS = 1  # Minimum delay between requests
MAX_DELAY_SECONDS = 3  # Maximum delay between requests
REQUEST_TIMEOUT = 30   # Request timeout
MAX_RETRIES = 3        # Maximum number of retries for failed requests

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.atg.wa.gov/'
}

def generate_incident_uid_wa(org_name: str, reported_date: str) -> str:
    """
    Generate a unique incident identifier for Washington AG breaches.
    """
    combined = f"wa_ag_{org_name.lower().strip()}_{reported_date}".replace(" ", "_")
    return hashlib.md5(combined.encode()).hexdigest()[:16]

def rate_limit_delay():
    """
    Add a random delay between requests to avoid overwhelming the server.
    """
    delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
    logger.debug(f"Rate limiting: waiting {delay:.1f} seconds")
    time.sleep(delay)

def parse_date_flexible_wa(date_str: str) -> str | None:
    """
    Enhanced date parsing for Washington AG with support for complex formats.
    Returns ISO format date string or None if parsing fails.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided', '']:
        return None

    date_str = date_str.strip()

    # Handle date ranges - take the first date
    if '–' in date_str:
        date_str = date_str.split('–')[0].strip()
    elif ' - ' in date_str:
        date_str = date_str.split(' - ')[0].strip()

    # Common formats to try
    formats = ['%m/%d/%Y', '%m/%d/%y', '%B %d, %Y', '%Y-%m-%d', '%d/%m/%Y']

    for fmt in formats:
        try:
            dt_object = datetime.strptime(date_str, fmt)
            return dt_object.isoformat()
        except ValueError:
            continue

    # Fallback to dateutil parser for complex formats
    try:
        dt_object = dateutil_parser.parse(date_str.strip())
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def parse_date_to_date_only(date_str: str) -> str | None:
    """
    Parse a date string and return just the date part (YYYY-MM-DD).
    If parsing fails, return the original string to preserve information.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided', '']:
        return None

    iso_date = parse_date_flexible_wa(date_str)
    if iso_date:
        return iso_date.split('T')[0]  # Extract just the date part

    # Return None rather than the raw string. breach_date and reported_date are DATE columns,
    # so handing them unparseable text makes the whole row insert fail and the breach is dropped
    # entirely. The original text is preserved in raw_data_json under the *_raw keys, so nothing
    # is lost by declining to guess here.
    logger.warning(f"Could not parse date '{date_str.strip()}'; storing NULL (raw text kept in raw_data_json)")
    return None

def is_recent_breach_wa(date_str: str) -> bool:
    """
    Check if a breach date is from the filter date onward.
    Returns True if the date is on or after the filter date.
    """
    if not date_str or not FILTER_FROM_DATE:
        return True  # Include all if no filtering

    try:
        breach_date = datetime.fromisoformat(date_str).date()
        filter_date = datetime.strptime(FILTER_FROM_DATE, '%Y-%m-%d').date()
        return breach_date >= filter_date
    except:
        return True  # Include if date parsing fails

def parse_affected_individuals_wa(affected_text: str) -> int | None:
    """
    Parse the affected individuals count from Washington AG text.
    Handles formats like "1,023", "14,255", "Unknown", etc.
    Returns integer if parseable, None if not a number.
    """
    if not affected_text or affected_text.strip().lower() in ['n/a', 'unknown', 'pending', 'tbd', 'not specified', '']:
        return None

    # Remove commas and extract numbers
    import re
    numbers = re.findall(r'[\d,]+', affected_text.strip())
    if numbers:
        try:
            # Take the first number found, remove commas
            number_str = numbers[0].replace(',', '')
            return int(number_str)
        except ValueError:
            pass

    # If no number found, return None (original text will be preserved in raw_data_json)
    return None

def parse_data_types_compromised_wa(data_types_text: str) -> list:
    """
    Parse the semicolon-separated data types from Washington AG "Information Compromised" column.
    Returns list of standardized data type categories.
    """
    if not data_types_text or data_types_text.strip().lower() in ['n/a', 'unknown', 'pending', 'not specified', '']:
        return []

    # Split by semicolon and clean up
    raw_types = [item.strip() for item in data_types_text.split(';') if item.strip()]

    # Map to standardized categories
    standardized_types = []
    for raw_type in raw_types:
        raw_lower = raw_type.lower()

        # Map common variations to standardized categories
        if 'social security' in raw_lower or 'ssn' in raw_lower:
            standardized_types.append('Social Security Numbers')
        elif 'driver' in raw_lower and 'license' in raw_lower:
            standardized_types.append('Driver License Numbers')
        elif 'financial' in raw_lower or 'banking' in raw_lower or 'account' in raw_lower:
            standardized_types.append('Financial Information')
        elif 'medical' in raw_lower or 'health' in raw_lower:
            standardized_types.append('Medical Information')
        elif 'passport' in raw_lower:
            standardized_types.append('Passport Numbers')
        elif 'biometric' in raw_lower:
            standardized_types.append('Biometric Data')
        elif 'insurance' in raw_lower:
            standardized_types.append('Insurance Information')
        elif 'birth' in raw_lower or 'date of birth' in raw_lower:
            standardized_types.append('Date of Birth')
        elif 'name' in raw_lower and len(raw_lower) < 20:  # Avoid long descriptions
            standardized_types.append('Personal Names')
        elif 'email' in raw_lower:
            standardized_types.append('Email Addresses')
        elif 'password' in raw_lower or 'username' in raw_lower:
            standardized_types.append('Login Credentials')
        else:
            # Keep original if no mapping found
            standardized_types.append(raw_type)

    # Remove duplicates while preserving order
    return list(dict.fromkeys(standardized_types))

def extract_pdf_url_wa(org_cell) -> str | None:
    """
    Extract PDF URL from organization name cell (which contains hyperlink to PDF).
    """
    if not org_cell:
        return None

    # Look for anchor tag with href
    link_tag = org_cell.find('a', href=True)
    if link_tag:
        href = link_tag.get('href', '')
        if href.endswith('.pdf'):
            # Return full URL (should already be absolute for S3 bucket)
            return href

    return None

def process_washington_ag_breaches():
    """
    Enhanced Washington AG Security Breach Notification processor with 3-tier data structure.
    Fetches breach notifications, processes with comprehensive field mapping, and inserts into Supabase.
    """
    logger.info("Starting Enhanced Washington AG Security Breach Notification processing...")

    if FILTER_FROM_DATE:
        logger.info(f"Date filtering enabled: collecting breaches from {FILTER_FROM_DATE} onward")
    else:
        logger.info("Date filtering disabled: collecting all historical breaches")

    try:
        response = requests.get(WASHINGTON_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        logger.info(f"Successfully fetched Washington AG breach data from {WASHINGTON_AG_BREACH_URL}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Washington AG breach data page from {WASHINGTON_AG_BREACH_URL}: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Find the main data table containing breach notifications
    # Based on Firecrawl analysis, the table has a clean structure with 5 columns
    data_table = soup.find('table')
    if not data_table:
        logger.error("No table found on the page. The page structure might have changed.")
        return

    tbody = data_table.find('tbody')
    if not tbody:
        # Try to get rows directly from table if no tbody
        notifications = data_table.find_all('tr')[1:]  # Skip header row
        if not notifications:
            logger.error("No data rows found in the table.")
            return
    else:
        notifications = tbody.find_all('tr')

    logger.info(f"Found {len(notifications)} breach notification rows in the table.")

    if not notifications:
        logger.warning("No breach notification rows found.")
        return

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    inserted_count = 0
    processed_count = 0
    skipped_count = 0

    # Process each breach notification row
    # Based on Firecrawl analysis, the table structure is:
    # Column 0: Date Reported
    # Column 1: Organization Name (with PDF link)
    # Column 2: Date of Breach
    # Column 3: Number of Washingtonians Affected
    # Column 4: Information Compromised


    for row_idx, row in enumerate(notifications):
        processed_count += 1
        cols = row.find_all(['td', 'th'])

        # Ensure we have the expected 5 columns
        if len(cols) < 5:
            logger.warning(f"Skipping row {row_idx+1} due to insufficient columns ({len(cols)}): {row.text[:100]}")
            skipped_count += 1
            continue

        try:
            # Extract data from the 5 columns based on known structure
            # Column 0: Date Reported
            # Column 1: Organization Name (with PDF link)
            # Column 2: Date of Breach
            # Column 3: Number of Washingtonians Affected
            # Column 4: Information Compromised

            date_reported_str = cols[0].get_text(strip=True)
            org_name = cols[1].get_text(strip=True)
            date_of_breach_str = cols[2].get_text(strip=True)
            residents_affected_str = cols[3].get_text(strip=True)
            information_compromised_str = cols[4].get_text(strip=True)

            # Extract PDF URL from organization name cell
            pdf_url = extract_pdf_url_wa(cols[1])

            if not org_name or not date_reported_str:
                logger.warning(f"Skipping row {row_idx+1} due to missing Organization Name ('{org_name}') or Date Reported ('{date_reported_str}')")
                skipped_count += 1
                continue

            # Parse dates with enhanced handling
            publication_date_iso = parse_date_flexible_wa(date_reported_str)
            if not publication_date_iso:
                # Try parsing breach date if reported date failed
                publication_date_iso = parse_date_flexible_wa(date_of_breach_str.split('-')[0].strip() if date_of_breach_str else None)
                if not publication_date_iso:
                    logger.warning(f"Skipping '{org_name}' due to unparsable dates: Reported='{date_reported_str}', Breach='{date_of_breach_str}'")
                    skipped_count += 1
                    continue
                else:
                    logger.info(f"Used breach date as publication date for '{org_name}' as reported date was unparsable.")

            # Apply date filtering
            if not is_recent_breach_wa(publication_date_iso):
                logger.info(f"Skipping '{org_name}' - breach date {publication_date_iso.split('T')[0]} is before filter date {FILTER_FROM_DATE}")
                skipped_count += 1
                continue

            # Parse structured data for dedicated fields
            affected_individuals = parse_affected_individuals_wa(residents_affected_str)
            breach_date_only = parse_date_to_date_only(date_of_breach_str)
            reported_date_only = parse_date_to_date_only(date_reported_str)
            data_types_compromised = parse_data_types_compromised_wa(information_compromised_str)

            # Generate incident UID for deduplication
            incident_uid = generate_incident_uid_wa(org_name, reported_date_only or date_reported_str)

            # Enhanced 3-tier raw_data_json structure
            raw_data = {
                # Tier 1: Portal Raw Data (direct from HTML table)
                "washington_ag_raw": {
                    "org_name": org_name,
                    "date_reported_raw": date_reported_str,
                    "date_of_breach_raw": date_of_breach_str,
                    "wa_residents_affected_raw": residents_affected_str,
                    "information_compromised_raw": information_compromised_str,
                    "pdf_url": pdf_url,
                    "table_row_index": row_idx,
                    "scrape_timestamp": datetime.now().isoformat()
                },

                # Tier 2: Derived/Housekeeping (computed fields)
                "washington_ag_derived": {
                    "incident_uid": incident_uid,
                    "portal_first_seen_utc": datetime.now().isoformat(),
                    "portal_last_seen_utc": datetime.now().isoformat(),
                    "affected_individuals_parsed": affected_individuals,
                    "data_types_standardized": data_types_compromised,
                    "has_pdf_notice": pdf_url is not None,
                    "breach_date_parsed": breach_date_only,
                    "reported_date_parsed": reported_date_only
                },

                # Tier 3: Deep Analysis (PDF content analysis - placeholder)
                "washington_ag_pdf_analysis": {
                    "pdf_processed": False,
                    "pdf_url": pdf_url,
                    "incident_description": None,
                    "detailed_data_types": None,
                    "timeline_details": None,
                    "credit_monitoring_offered": None,
                    "pdf_text_blob": None,
                    "pdf_analysis_error": "PDF analysis not yet implemented"
                }
            }

            # Create comprehensive summary
            summary_parts = []
            if reported_date_only:
                summary_parts.append(f"Reported to Washington AG: {reported_date_only}")
            if breach_date_only:
                summary_parts.append(f"Breach occurred: {breach_date_only}")
            if affected_individuals:
                summary_parts.append(f"Washington residents affected: {affected_individuals:,}")
            elif residents_affected_str and residents_affected_str.lower() != 'unknown':
                summary_parts.append(f"Washington residents affected: {residents_affected_str}")
            if data_types_compromised:
                summary_parts.append(f"Data types: {', '.join(data_types_compromised[:3])}{'...' if len(data_types_compromised) > 3 else ''}")
            if pdf_url:
                summary_parts.append("Official notice available")

            summary = ". ".join(summary_parts) + "." if summary_parts else "Data breach notification."

            # Generate unique URL
            if pdf_url:
                unique_url = pdf_url
            else:
                import urllib.parse
                org_slug = urllib.parse.quote(org_name.replace(' ', '-').lower())
                date_slug = publication_date_iso.split('T')[0]
                unique_url = f"{WASHINGTON_AG_BREACH_URL}#{org_slug}-{date_slug}"

            # Enhanced tags based on data types
            tags = ["washington_ag", "wa_breach", "data_breach"]
            for data_type in data_types_compromised:
                if "Social Security" in data_type:
                    tags.append("ssn_breach")
                elif "Medical" in data_type:
                    tags.append("healthcare_breach")
                elif "Financial" in data_type:
                    tags.append("financial_breach")

            item_data = {
                "source_id": SOURCE_ID_WASHINGTON_AG,
                "item_url": unique_url,
                "title": org_name,
                "publication_date": publication_date_iso,
                "summary_text": summary.strip(),
                "raw_data_json": raw_data,
                "tags_keywords": list(set(tags)),

                # Standardized breach fields (existing schema)
                "affected_individuals": affected_individuals,
                "breach_date": breach_date_only,
                "reported_date": reported_date_only,
                "notice_document_url": pdf_url,

                # Enhanced fields for comprehensive data capture
                "data_types_compromised": data_types_compromised,
                "exhibit_urls": [pdf_url] if pdf_url else None,
                "keywords_detected": data_types_compromised + ["washington", "breach", "notification"],
                "keyword_contexts": None  # Will be populated from PDF analysis
            }

            # Check for existing record before inserting
            try:
                query_result = supabase_client.client.table("scraped_items").select("id").eq("title", org_name).eq("publication_date", publication_date_iso).eq("source_id", SOURCE_ID_WASHINGTON_AG).execute()
                if query_result.data:
                    logger.info(f"Item '{org_name}' on {publication_date_iso} already exists. Skipping.")
                    skipped_count += 1
                    continue
            except Exception as e_check:
                logger.warning(f"Could not check for existing record: {e_check}. Proceeding with insert.")

            try:
                insert_response = supabase_client.insert_item(**item_data)
                if insert_response:
                    logger.info(f"Successfully inserted item for '{org_name}'. URL: {item_data['item_url']}")
                    inserted_count += 1
                else:
                    logger.error(f"Failed to insert item for '{org_name}'. Supabase client returned no error, but no data in response.")
            except Exception as e_insert:
                if "duplicate key value violates unique constraint" in str(e_insert):
                    logger.info(f"Item '{org_name}' already exists (duplicate URL). Skipping.")
                    skipped_count += 1
                else:
                    logger.error(f"Error inserting item for '{org_name}' into Supabase: {e_insert}")
                    skipped_count += 1

        except Exception as e:
            logger.error(f"Error processing row for '{org_name if 'org_name' in locals() else 'Unknown Entity'}': {row.text[:150]}. Error: {e}", exc_info=True)
            skipped_count += 1

    logger.info(f"Finished processing Washington AG breaches. Total rows processed: {processed_count}. Items inserted: {inserted_count}. Items skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("Washington AG Security Breach Scraper Started")

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_washington_ag_breaches()

    logger.info("Washington AG Security Breach Scraper Finished")
