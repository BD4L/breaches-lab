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
SOUTH_CAROLINA_AG_BREACH_URL = "https://consumer.sc.gov/identity-theft-unit/security-breach-notices"
SOURCE_ID_SOUTH_CAROLINA_AG = 38  # ID 38 for South Carolina AG

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_sc(date_str: str) -> str | None:
    """
    Enhanced date parsing for South Carolina AG with support for various formats.
    Handles M/D/YYYY format primarily used by SC AG.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided']:
        return None

    date_str = date_str.strip()

    # Common formats to try (SC AG uses M/D/YYYY format)
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

def parse_affected_individuals(affected_text: str) -> int | None:
    """
    Parse the affected individuals count from text.
    Handles formats like "1,023", "14,255", "N/A", etc.
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

def generate_incident_uid(org_name: str, reported_date: str) -> str:
    """
    Generate a unique incident identifier based on org name and reported date.
    """
    import hashlib
    combined = f"{org_name.lower().strip()}_{reported_date}"
    return hashlib.md5(combined.encode()).hexdigest()[:12]

def parse_date_to_date_only(date_str: str) -> str | None:
    """
    Parse a date string and return just the date part (YYYY-MM-DD).
    If parsing fails, return the original string to preserve information.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided']:
        return None

    iso_date = parse_date_sc(date_str)
    if iso_date:
        return iso_date.split('T')[0]  # Extract just the date part

    # Return None rather than the raw string. breach_date and reported_date are DATE columns,
    # so handing them unparseable text makes the whole row insert fail and the breach is dropped
    # entirely. The original text is preserved in raw_data_json under the *_raw keys, so nothing
    # is lost by declining to guess here.
    logger.warning(f"Could not parse date '{date_str.strip()}'; storing NULL (raw text kept in raw_data_json)")
    return None

def process_south_carolina_ag_breaches():
    """
    Fetches South Carolina AG security breach notifications, processes each notification,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting South Carolina AG Security Breach Notification processing...")

    try:
        response = requests.get(SOUTH_CAROLINA_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching South Carolina AG breach data page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Look for the table containing breach data
    table = soup.find('table')
    if not table:
        logger.error("Could not find any table on the page. The page structure might have changed.")
        return

    # Get all rows (including header)
    rows = table.find_all('tr')
    if len(rows) <= 1:
        logger.error("Could not find data rows in the table. Page structure might have changed.")
        return

    # Skip header row
    data_rows = rows[1:]
    logger.info(f"Found {len(data_rows)} potential breach notifications on the page.")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    inserted_count = 0
    processed_count = 0
    skipped_count = 0

    for row in data_rows:
        processed_count += 1
        cols = row.find_all('td')
        if len(cols) < 3:  # Expecting 3 columns: Organization Name, Date Reported, Affected SC Residents
            logger.warning(f"Skipping row due to insufficient columns ({len(cols)}): {row.text[:100]}")
            skipped_count += 1
            continue

        try:
            # Column order based on the table structure:
            # 0: Organization Name (with PDF link)
            # 1: Date Reported
            # 2: Affected SC Residents

            # Extract organization name and PDF link
            org_cell = cols[0]
            org_link = org_cell.find('a', href=True)
            if org_link:
                entity_name = org_link.get_text(strip=True)
                pdf_url = urljoin(SOUTH_CAROLINA_AG_BREACH_URL, org_link['href'])
            else:
                entity_name = org_cell.get_text(strip=True)
                pdf_url = None

            reported_date_str = cols[1].get_text(strip=True)
            residents_affected_text = cols[2].get_text(strip=True)

            if not entity_name:
                logger.warning(f"Skipping row due to missing entity name: {row.text[:100]}")
                skipped_count += 1
                continue

            # Parse the reported date for publication_date
            publication_date_iso = None
            original_publication_date = None

            if reported_date_str and reported_date_str.lower() not in ['n/a', 'unknown', '']:
                publication_date_iso = parse_date_sc(reported_date_str)
                if publication_date_iso:
                    original_publication_date = publication_date_iso

            # If no valid date could be parsed, use current date as fallback to preserve the record
            current_datetime_iso = datetime.now().isoformat()
            if not publication_date_iso:
                publication_date_iso = current_datetime_iso
                logger.info(f"Using current date as fallback for '{entity_name}' - preserving record with unparsable date. Reported: '{reported_date_str}'")

            # Filter: Only collect breaches from June 1st, 2025 onward
            # But only apply this filter if we successfully parsed a real date (not using fallback)
            if original_publication_date and not is_recent_breach(original_publication_date):
                logger.info(f"Skipping '{entity_name}' - reported date {original_publication_date.split('T')[0]} is before June 1st, 2025")
                skipped_count += 1
                continue

            # Parse structured data for dedicated fields
            affected_individuals = parse_affected_individuals(residents_affected_text)
            reported_date_only = parse_date_to_date_only(reported_date_str)

            # Generate derived fields
            incident_uid = generate_incident_uid(entity_name, reported_date_only or reported_date_str)

            # Enhanced raw_data_json structure following established pattern
            raw_data = {
                # A. Raw extraction (direct from HTML table)
                "south_carolina_ag_raw": {
                    "org_name": entity_name,
                    "reported_date_raw": reported_date_str,
                    "sc_residents_affected_raw": residents_affected_text,
                    "pdf_notice_url": pdf_url,
                    "listing_year": datetime.now().year
                },

                # B. Derived/enrichment (computed fields)
                "south_carolina_ag_derived": {
                    "incident_uid": incident_uid,
                    "portal_first_seen_utc": datetime.now().isoformat(),
                    "portal_last_seen_utc": datetime.now().isoformat(),
                    "has_pdf_notice": pdf_url is not None
                },

                # C. Deep-dive from PDF (placeholder for future implementation)
                "south_carolina_ag_pdf_analysis": {
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
            }

            # Clean up the raw data (remove empty/null values)
            raw_data_json = {k: v for k, v in raw_data.items() if v is not None}

            # Create comprehensive summary from available information
            summary_parts = []
            if reported_date_str and reported_date_str.strip() and reported_date_str.lower() not in ['n/a', 'unknown', '']:
                summary_parts.append(f"Reported to South Carolina AG: {reported_date_str}")
            if residents_affected_text and residents_affected_text.strip() and residents_affected_text.lower() not in ['n/a', 'unknown', '']:
                summary_parts.append(f"South Carolina residents affected: {residents_affected_text}")
            if pdf_url:
                summary_parts.append("Consumer notice document available")

            summary = ". ".join(summary_parts) + "." if summary_parts else "Data breach notification."

            # Generate stable unique URL
            item_specific_url = pdf_url if pdf_url else f"{SOUTH_CAROLINA_AG_BREACH_URL}#{incident_uid}"

            item_data = {
                "source_id": SOURCE_ID_SOUTH_CAROLINA_AG,
                "item_url": item_specific_url,
                "title": entity_name,
                "publication_date": publication_date_iso,
                "summary_text": summary.strip(),
                "raw_data_json": raw_data_json,
                "tags_keywords": ["south_carolina_ag", "sc_breach", "data_breach"],

                # Standardized breach fields (existing schema)
                "affected_individuals": affected_individuals,
                "breach_date": None,  # SC AG doesn't provide breach date, only reported date
                "reported_date": reported_date_only,
                "notice_document_url": pdf_url,

                # Map to existing schema fields for future PDF analysis
                "exhibit_urls": [pdf_url] if pdf_url else None,  # Document links
                "data_types_compromised": None,  # Will be populated from PDF analysis
                "incident_discovery_date": None,  # Will be extracted from PDF
                "incident_disclosure_date": None,  # Will be extracted from PDF
                "keywords_detected": ["data_breach", "south_carolina", "notification"],  # Basic keywords
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
                query_result = supabase_client.client.table("scraped_items").select("id").eq("item_url", item_specific_url).eq("source_id", SOURCE_ID_SOUTH_CAROLINA_AG).execute()
                if query_result.data:
                    logger.info(f"Item '{entity_name}' with URL {item_specific_url} already exists. Skipping.")
                    skipped_count += 1
                    continue

                # Secondary check by incident_uid in raw_data_json
                query_result = supabase_client.client.table("scraped_items").select("id, raw_data_json").eq("title", entity_name).eq("source_id", SOURCE_ID_SOUTH_CAROLINA_AG).execute()
                duplicate_by_uid = any(
                    ((existing_item.get('raw_data_json') or {})
                     .get('south_carolina_ag_derived', {})
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
            skipped_count += 1

    logger.info(f"Finished processing South Carolina AG breaches. Total rows processed: {processed_count}. Items inserted: {inserted_count}. Items skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("South Carolina AG Security Breach Scraper Started")

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_south_carolina_ag_breaches()

    logger.info("South Carolina AG Security Breach Scraper Finished")
