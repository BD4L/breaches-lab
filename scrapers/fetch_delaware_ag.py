import os
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin

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
DELAWARE_AG_BREACH_URL = "https://attorneygeneral.delaware.gov/fraud/cpu/securitybreachnotification/database/"
SOURCE_ID_DELAWARE_AG = 3 # Placeholder for Delaware AG

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_delaware(date_str: str) -> str | None:
    """
    Enhanced date parsing for Delaware AG with support for complex formats.
    Handles date ranges, concatenated dates, and various formats.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided']:
        return None

    date_str = date_str.strip()

    # Handle date ranges - take the first date
    if '–' in date_str:
        date_str = date_str.split('–')[0].strip()
    elif ' - ' in date_str:
        date_str = date_str.split(' - ')[0].strip()

    # Handle concatenated dates without separators (like "04/09/202504/21/2025")
    if date_str.count('/') >= 4:  # Multiple dates concatenated
        # Try to extract the first complete date
        import re
        match = re.match(r'(\d{1,2}/\d{1,2}/\d{4})', date_str)
        if match:
            date_str = match.group(1)

    # Handle multiple dates separated by spaces or newlines
    if '\n' in date_str or '  ' in date_str:
        # Take the first date-like string
        parts = date_str.replace('\n', ' ').split()
        for part in parts:
            if '/' in part and len(part) >= 8:  # Looks like a date
                date_str = part
                break

    # Common formats to try
    formats = ['%m/%d/%Y', '%m/%d/%y', '%B %d, %Y', '%Y-%m-%d', '%d/%m/%Y']

    for fmt in formats:
        try:
            dt_object = datetime.strptime(date_str, fmt)
            return dt_object.isoformat()
        except ValueError:
            continue

    logger.warning(f"Could not parse date string: '{date_str}' with formats {formats}")
    return None

def is_recent_breach(date_str: str) -> bool:
    """
    Check if a breach date is from June 1st, 2025 onward.
    Returns True if the date is on or after June 1st, 2025.
    """
    if not date_str:
        return True  # Include if no date available

    try:
        from datetime import datetime, date
        breach_date = datetime.fromisoformat(date_str).date()
        cutoff_date = date(2025, 6, 1)  # June 1st, 2025
        return breach_date >= cutoff_date
    except:
        return True  # Include if date parsing fails

def extract_organization_name(cell) -> tuple[str, str]:
    """
    Extract organization name and row notes from potentially complex cell structure.
    Some cells have nested tables or complex HTML.
    Returns: (org_name, row_notes)
    """
    # First try to get text directly
    text = cell.get_text(strip=True)
    if not text or text.isspace():
        # If that fails, look for nested tables
        nested_table = cell.find('table')
        if nested_table:
            # Get text from the first cell of the nested table
            first_cell = nested_table.find('td')
            if first_cell:
                text = first_cell.get_text(strip=True)
            else:
                return "", ""
        else:
            return "", ""

    # Extract row notes (text in parentheses like "(Supplemental)" or "(Addendum)")
    import re
    row_notes = ""
    notes_match = re.search(r'\((.*?)\)', text)
    if notes_match:
        row_notes = notes_match.group(1)
        # Remove the notes from the org name
        text = re.sub(r'\s*\([^)]*\)', '', text).strip()

    return text, row_notes

def generate_incident_uid(org_name: str, breach_date: str) -> str:
    """
    Generate a unique incident identifier based on org name and breach date.
    """
    import hashlib
    combined = f"{org_name.lower().strip()}_{breach_date}"
    return hashlib.md5(combined.encode()).hexdigest()[:12]

def check_multiple_dates(date_str: str) -> bool:
    """
    Check if the date string contains multiple dates or date types.
    """
    if not date_str:
        return False

    # Look for indicators of multiple dates
    indicators = ['substitute', 'media', 'and', '&', 'multiple', 'various']
    date_str_lower = date_str.lower()

    # Count date-like patterns
    import re
    date_patterns = re.findall(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', date_str)

    return len(date_patterns) > 1 or any(indicator in date_str_lower for indicator in indicators)

def analyze_pdf_notice(pdf_url: str) -> dict:
    """
    Future function to analyze PDF notice documents.
    This is a placeholder for PDF analysis functionality.

    Args:
        pdf_url: URL to the PDF notice document

    Returns:
        Dictionary with extracted PDF data following your schema
    """
    # TODO: Implement PDF analysis using pdfminer or Apache Tika
    # This would extract:
    # - incident_description (first paragraph under "What Happened?")
    # - data_types_compromised (keywords from "What Information Was Involved?")
    # - date_discovered (regex for "discovered on <date>")
    # - date_contained/date_confirmed
    # - credit_monitoring_offered (Y/N) and monitoring_duration_months
    # - consumer_callcenter_phone
    # - regulator_contact or AG_reference_no
    # - pdf_text_blob (full text for future re-parse)

    return {
        "pdf_processed": False,
        "incident_description": None,
        "data_types_compromised": [],
        "date_discovered": None,
        "date_contained": None,
        "credit_monitoring_offered": None,
        "monitoring_duration_months": None,
        "consumer_callcenter_phone": None,
        "regulator_contact": None,
        "pdf_text_blob": None,
        "pdf_analysis_error": "PDF analysis not yet implemented"
    }

def parse_affected_individuals(affected_text: str) -> int | None:
    """
    Parse the affected individuals count from text.
    Handles formats like "1,023", "14,255", "N/A", etc.
    Returns integer if parseable, None if not a number.
    """
    if not affected_text or affected_text.strip().lower() in ['n/a', 'unknown', 'pending', 'tbd', 'not specified']:
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

def parse_date_to_date_only(date_str: str) -> str | None:
    """
    Parse a date string and return just the date part (YYYY-MM-DD).
    If parsing fails, return the original string to preserve information.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided']:
        return None

    iso_date = parse_date_delaware(date_str)
    if iso_date:
        return iso_date.split('T')[0]  # Extract just the date part

    # Return None rather than the raw string. breach_date and reported_date are DATE columns,
    # so handing them unparseable text makes the whole row insert fail and the breach is dropped
    # entirely. The original text is preserved in raw_data_json under the *_raw keys, so nothing
    # is lost by declining to guess here.
    logger.warning(f"Could not parse date '{date_str.strip()}'; storing NULL (raw text kept in raw_data_json)")
    return None

def process_delaware_ag_breaches():
    """
    Fetches Delaware AG security breach notifications, processes each notification,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting Delaware AG Security Breach Notification processing...")

    try:
        response = requests.get(DELAWARE_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Delaware AG breach data page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # The data is within a DataTable (no specific ID, but it's the main table on the page)
    # Look for the table containing breach data
    table = soup.find('table')
    if not table:
        logger.error("Could not find any table on the page. The page structure might have changed.")
        return

    tbody = table.find('tbody')
    if not tbody:
        logger.error("Could not find the table body (tbody) for breaches. Page structure might have changed.")
        return

    notifications = tbody.find_all('tr')
    logger.info(f"Found {len(notifications)} potential breach notifications on the page.")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    inserted_count = 0
    processed_count = 0
    skipped_count = 0

    for row in notifications:
        processed_count += 1
        cols = row.find_all('td')
        if len(cols) < 5: # Expecting at least 5 columns based on current table structure
            logger.warning(f"Skipping row due to insufficient columns ({len(cols)}): {row.text[:100]}")
            skipped_count += 1
            continue

        try:
            # Current column order (as of 2025):
            # 0: Organization Name
            # 1: Date(s) of Breach
            # 2: Reported Date (to AG)
            # 3: Number of Potentially Affected Delaware Residents
            # 4: Sample of Notice (contains PDF link)

            # Use improved organization name extraction with row notes
            entity_name, row_notes = extract_organization_name(cols[0])
            date_of_breach_str = cols[1].get_text(strip=True)
            reported_date_str = cols[2].get_text(strip=True)
            residents_affected_text = cols[3].get_text(strip=True)

            # Link to detailed notice is in the 'Sample of Notice' column
            detailed_notice_link_tag = cols[4].find('a', href=True)
            item_specific_url = None
            if detailed_notice_link_tag:
                item_specific_url = urljoin(DELAWARE_AG_BREACH_URL, detailed_notice_link_tag['href'])

            if not entity_name:
                logger.warning(f"Skipping row due to missing entity name: {row.text[:100]}")
                skipped_count += 1
                continue

            # Prioritize reported date (to AG), then breach date for publication_date
            publication_date_iso = None
            original_publication_date = None  # Track if we used a real date or fallback

            if reported_date_str and reported_date_str.lower() not in ['n/a', 'unknown', '']:
                publication_date_iso = parse_date_delaware(reported_date_str)
                if publication_date_iso:
                    original_publication_date = publication_date_iso

            if not publication_date_iso and date_of_breach_str and date_of_breach_str.lower() not in ['n/a', 'unknown', '']:
                publication_date_iso = parse_date_delaware(date_of_breach_str)
                if publication_date_iso:
                    original_publication_date = publication_date_iso

            # If no valid date could be parsed, use current date as fallback to preserve the record
            current_datetime_iso = datetime.now().isoformat()
            if not publication_date_iso:
                publication_date_iso = current_datetime_iso
                logger.info(f"Using current date as fallback for '{entity_name}' - preserving record with unparsable dates. Reported: '{reported_date_str}', Breach: '{date_of_breach_str}'")

            # Filter: Only collect breaches from today onward (exclude archived/past listings)
            # But only apply this filter if we successfully parsed a real date (not using fallback)
            if original_publication_date and not is_recent_breach(original_publication_date):
                logger.info(f"Skipping '{entity_name}' - breach date {original_publication_date.split('T')[0]} is before today")
                skipped_count += 1
                continue

            # Parse structured data for dedicated fields
            affected_individuals = parse_affected_individuals(residents_affected_text)
            breach_date_only = parse_date_to_date_only(date_of_breach_str)
            reported_date_only = parse_date_to_date_only(reported_date_str)

            # Enhanced raw_data_json structure following your proposed schema
            # Generate derived fields
            incident_uid = generate_incident_uid(entity_name, breach_date_only or date_of_breach_str)
            is_supplemental = "supplemental" in row_notes.lower() or "addendum" in row_notes.lower()
            seen_multiple_dates = check_multiple_dates(reported_date_str)

            raw_data = {
                # A. Raw extraction (direct from HTML table)
                "delaware_ag_raw": {
                    "org_name": entity_name,
                    "breach_date_raw": date_of_breach_str,
                    "reported_date_raw": reported_date_str,
                    "de_residents_affected_raw": residents_affected_text,
                    "sample_notice_url": item_specific_url if item_specific_url else None,
                    "row_notes": row_notes,
                    "listing_year": datetime.now().year  # TODO: Extract from page heading if available
                },

                # B. Derived/enrichment (computed fields)
                "delaware_ag_derived": {
                    "incident_uid": incident_uid,
                    "portal_first_seen_utc": datetime.now().isoformat(),
                    "portal_last_seen_utc": datetime.now().isoformat(),
                    "is_supplemental": is_supplemental,
                    "breach_duration_days": None,  # TODO: calculate if start & end dates parsed
                    "seen_multiple_report_dates": seen_multiple_dates
                },

                # C. Deep-dive from PDF (placeholder for future implementation)
                "delaware_ag_pdf_analysis": {
                    "pdf_processed": False,
                    "incident_description": None,
                    "data_types_compromised": [],
                    "date_discovered": None,
                    "date_contained": None,
                    "credit_monitoring_offered": None,
                    "monitoring_duration_months": None,
                    "consumer_callcenter_phone": None,
                    "regulator_contact": None,
                    "pdf_text_blob": None
                }
            }

            # Clean up the raw data (remove empty/null values)
            raw_data_json = {k: v for k, v in raw_data.items() if v is not None}

            # Create comprehensive summary from available information
            summary_parts = []
            if reported_date_str and reported_date_str.strip() and reported_date_str.lower() not in ['n/a', 'unknown', '']:
                summary_parts.append(f"Reported to Delaware AG: {reported_date_str}")
            if date_of_breach_str and date_of_breach_str.strip() and date_of_breach_str.lower() not in ['n/a', 'unknown', '']:
                summary_parts.append(f"Breach occurred: {date_of_breach_str}")
            if residents_affected_text and residents_affected_text.strip() and residents_affected_text.lower() not in ['n/a', 'unknown', '']:
                summary_parts.append(f"Delaware residents affected: {residents_affected_text}")
            if item_specific_url:
                summary_parts.append("Sample notice available")

            summary = ". ".join(summary_parts) + "." if summary_parts else "Data breach notification."


            # Generate stable unique URL if no specific URL available
            if not item_specific_url:
                import urllib.parse
                org_slug = urllib.parse.quote(entity_name.replace(' ', '-').lower())
                # Use incident_uid for stable URL instead of current date
                item_specific_url = f"{DELAWARE_AG_BREACH_URL}#{org_slug}-{incident_uid}"

            item_data = {
                "source_id": SOURCE_ID_DELAWARE_AG,
                "item_url": item_specific_url,
                "title": entity_name,
                "publication_date": publication_date_iso,
                "summary_text": summary.strip(),
                "raw_data_json": raw_data_json,
                "tags_keywords": ["delaware_ag", "de_breach", "data_breach"],

                # Standardized breach fields (existing schema)
                "affected_individuals": affected_individuals,
                "breach_date": breach_date_only,
                "reported_date": reported_date_only,
                "notice_document_url": item_specific_url if item_specific_url else None,

                # Map to existing schema fields for future PDF analysis
                "exhibit_urls": [item_specific_url] if item_specific_url else None,  # Document links
                "data_types_compromised": None,  # Will be populated from PDF analysis
                "incident_discovery_date": None,  # Will be extracted from PDF
                "incident_disclosure_date": None,  # Will be extracted from PDF
                "keywords_detected": ["data_breach", "delaware", "notification"],  # Basic keywords
                "keyword_contexts": None  # Will be populated from PDF text analysis
            }

            # Check for existing record using stable identifiers
            # Set by the incident_uid check below. It cannot use `continue` directly, because
            # that check runs inside an inner loop over candidate rows, so `continue` there only
            # advanced the inner loop and execution fell through to the insert anyway — the
            # duplicate was logged as skipped, counted as skipped, and then inserted.
            duplicate_by_uid = False

            try:
                # First check by URL (most reliable)
                query_result = supabase_client.client.table("scraped_items").select("id").eq("item_url", item_specific_url).eq("source_id", SOURCE_ID_DELAWARE_AG).execute()
                if query_result.data:
                    logger.info(f"Item '{entity_name}' with URL {item_specific_url} already exists. Skipping.")
                    skipped_count += 1
                    continue

                # Secondary check by incident_uid in raw_data_json
                query_result = supabase_client.client.table("scraped_items").select("id, raw_data_json").eq("title", entity_name).eq("source_id", SOURCE_ID_DELAWARE_AG).execute()
                duplicate_by_uid = any(
                    ((existing_item.get('raw_data_json') or {})
                     .get('delaware_ag_derived', {})
                     .get('incident_uid')) == incident_uid
                    for existing_item in (query_result.data or [])
                )
                if duplicate_by_uid:
                    logger.info(f"Item '{entity_name}' with incident_uid {incident_uid} already exists. Skipping.")
                    skipped_count += 1

            except Exception as e_check:
                logger.warning(f"Could not check for existing record: {e_check}. Proceeding with insert.")

            if duplicate_by_uid:
                continue

            try:
                insert_response = supabase_client.insert_item(**item_data)
                if insert_response:
                    logger.info(f"Successfully inserted item for '{entity_name}'.")
                    inserted_count += 1
                else:
                    logger.error(f"Failed to insert item for '{entity_name}'.")
            except Exception as e_insert:
                if "duplicate key value violates unique constraint" in str(e_insert):
                    logger.info(f"Item '{entity_name}' already exists (duplicate URL). Skipping.")
                    skipped_count += 1
                else:
                    logger.error(f"Error inserting item for '{entity_name}' into Supabase: {e_insert}")
                    skipped_count += 1

        except Exception as e:
            logger.error(f"Error processing row for '{entity_name if 'entity_name' in locals() else 'Unknown Entity'}': {row.text[:150]}. Error: {e}", exc_info=True)
            skipped_count +=1

    logger.info(f"Finished processing Delaware AG breaches. Total rows processed: {processed_count}. Items inserted: {inserted_count}. Items skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("Delaware AG Security Breach Scraper Started")

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_delaware_ag_breaches()

    logger.info("Delaware AG Security Breach Scraper Finished")
