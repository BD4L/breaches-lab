import os
import logging
import requests
import hashlib
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
import re

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
HHS_OCR_BREACH_URL = "https://ocrportal.hhs.gov/ocr/breach/breach_report.jsf"
SOURCE_ID_HHS_OCR = 2  # HHS OCR Breach Portal

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_hhs(date_str: str) -> str | None:
    """
    Parse HHS OCR date strings (typically MM/DD/YYYY format).
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending']:
        return None

    date_str = date_str.strip()
    formats = ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%B %d, %Y"]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).isoformat()
        except ValueError:
            continue

    logger.warning(f"Could not parse HHS OCR date string: '{date_str}'")
    return None

def generate_ocr_incident_uid(covered_entity_name: str, breach_submission_date: str) -> str:
    """
    Generate OCR incident UID following your proposed schema.
    Uses hash of covered_entity_name + breach_submission_date since OCR doesn't provide stable IDs.
    """
    combined = f"{covered_entity_name.lower().strip()}_{breach_submission_date}"
    return hashlib.md5(combined.encode()).hexdigest()[:12]

def parse_individuals_affected(affected_str: str) -> tuple[int | None, str]:
    """
    Parse individuals affected, handling edge cases like "0" or "<500".
    Returns: (parsed_integer, raw_string)
    """
    if not affected_str:
        return None, ""

    affected_str = affected_str.strip()
    raw_string = affected_str

    # Handle special cases
    if affected_str.lower() in ['n/a', 'unknown', 'pending', 'tbd']:
        return None, raw_string

    # Remove commas and extract numbers
    numbers = re.findall(r'[\d,]+', affected_str)
    if numbers:
        try:
            number_str = numbers[0].replace(',', '')
            return int(number_str), raw_string
        except ValueError:
            pass

    return None, raw_string

def parse_location_breached(location_str: str) -> list[str]:
    """
    Parse location of breached information into array.
    Handles comma-separated values like "Network Server, Email".
    """
    if not location_str:
        return []

    # Split by comma and clean up
    locations = [loc.strip() for loc in location_str.split(',') if loc.strip()]
    return locations

def extract_data_types_from_description(description: str) -> list[str]:
    """
    Extract data types compromised from web description using regex patterns.
    This implements Layer C of your proposed schema.
    """
    if not description:
        return []

    description_lower = description.lower()
    data_types = []

    # Common PHI/PII patterns
    patterns = {
        'ssn': r'social security|ssn|social security number',
        'financial': r'financial|credit card|bank|account number|payment',
        'clinical': r'medical|clinical|health|diagnosis|treatment|prescription',
        'demographic': r'name|address|phone|email|date of birth|dob',
        'insurance': r'insurance|policy|member id|subscriber',
        'biometric': r'biometric|fingerprint|facial|retinal'
    }

    for data_type, pattern in patterns.items():
        if re.search(pattern, description_lower):
            data_types.append(data_type)

    return data_types

def extract_discovery_date(description: str) -> str | None:
    """
    Extract discovery date from web description using regex.
    Looks for patterns like "discovered on [date]".
    """
    if not description:
        return None

    # Common discovery date patterns
    patterns = [
        r'discovered on (\d{1,2}/\d{1,2}/\d{4})',
        r'discovered (\d{1,2}/\d{1,2}/\d{4})',
        r'became aware on (\d{1,2}/\d{1,2}/\d{4})',
        r'learned of.*on (\d{1,2}/\d{1,2}/\d{4})'
    ]

    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            date_str = match.group(1)
            return parse_date_hhs(date_str)

    return None

def check_credit_monitoring(description: str) -> tuple[bool | None, int | None]:
    """
    Check if credit monitoring is offered and extract duration.
    Returns: (is_offered, duration_months)
    """
    if not description:
        return None, None

    description_lower = description.lower()

    # Check for credit monitoring mentions
    monitoring_patterns = [
        r'credit monitoring',
        r'identity monitoring',
        r'identity protection',
        r'credit protection'
    ]

    is_offered = any(re.search(pattern, description_lower) for pattern in monitoring_patterns)

    # Extract duration
    duration = None
    duration_patterns = [
        r'(\d+)\s*year.*monitoring',
        r'(\d+)\s*month.*monitoring',
        r'monitoring.*(\d+)\s*year',
        r'monitoring.*(\d+)\s*month'
    ]

    for pattern in duration_patterns:
        match = re.search(pattern, description_lower)
        if match:
            num = int(match.group(1))
            if 'year' in pattern:
                duration = num * 12
            else:
                duration = num
            break

    return is_offered if is_offered else None, duration

def process_hhs_ocr_breaches():
    """
    Fetches HHS OCR breach data from the HTML portal and processes each record
    using the 3-tier approach: Raw extraction Derived/enrichment Deep analysis.

    Since CSV export is not available, we scrape the HTML table directly.
    """
    logger.info("Starting HHS OCR Breach Report processing...")

    try:
        response = requests.get(HHS_OCR_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching HHS OCR breach data page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Find the main data table (it's the second table on the page)
    # The first table contains only informational text
    tables = soup.find_all('table')
    if len(tables) < 2:
        logger.error("Could not find the breach data table. Expected at least 2 tables on the page.")
        return

    # The actual breach data is in the second table
    table = tables[1]

    # Verify this is the correct table by checking for expected headers
    headers = [th.get_text(strip=True) for th in table.find_all('th')]
    if 'Name of Covered Entity' not in headers:
        logger.error("Found table but it doesn't contain expected headers. Page structure might have changed.")
        logger.error(f"Found headers: {headers}")
        return

    tbody = table.find('tbody')
    if not tbody:
        logger.error("Could not find table body (tbody) for breaches. Page structure might have changed.")
        return

    rows = tbody.find_all('tr')
    logger.info(f"Found {len(rows)} potential breach records on the page.")
    logger.info(f"Table headers: {headers}")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    inserted_count = 0
    processed_count = 0
    skipped_count = 0

    for row in rows:
        processed_count += 1
        cols = row.find_all('td')

        # Expected columns based on portal analysis:
        # 0: Expand All (skip)
        # 1: Name of Covered Entity
        # 2: State
        # 3: Covered Entity Type
        # 4: Individuals Affected
        # 5: Breach Submission Date
        # 6: Type of Breach
        # 7: Location of Breached Information
        # 8: Business Associate Present
        # 9: Web Description

        if len(cols) < 9:  # Need at least 9 columns for complete data
            logger.warning(f"Skipping row due to insufficient columns ({len(cols)}). Row content: {[col.get_text(strip=True)[:50] for col in cols]}")
            skipped_count += 1
            continue

        try:
            # A. Raw extraction (Layer A from your schema)
            covered_entity_name = cols[1].get_text(strip=True)
            state = cols[2].get_text(strip=True)
            entity_type = cols[3].get_text(strip=True)
            individuals_affected_raw = cols[4].get_text(strip=True)
            breach_submission_date_str = cols[5].get_text(strip=True)
            breach_type = cols[6].get_text(strip=True)
            location_breached_raw = cols[7].get_text(strip=True)
            business_associate_present = cols[8].get_text(strip=True)
            web_description = cols[9].get_text(strip=True) if len(cols) > 9 else ""

            if not covered_entity_name or not breach_submission_date_str:
                logger.warning(f"Skipping row due to missing entity name or submission date")
                skipped_count += 1
                continue

            # Parse and validate submission date
            publication_date_iso = parse_date_hhs(breach_submission_date_str)
            if not publication_date_iso:
                logger.warning(f"Skipping '{covered_entity_name}' due to unparsable date: {breach_submission_date_str}")
                skipped_count += 1
                continue

            # B. Derived/enrichment (Layer B from your schema)
            individuals_affected, individuals_affected_raw_clean = parse_individuals_affected(individuals_affected_raw)
            location_breached_array = parse_location_breached(location_breached_raw)
            ocr_incident_uid = generate_ocr_incident_uid(covered_entity_name, breach_submission_date_str)
            breach_year = datetime.fromisoformat(publication_date_iso).year

            # C. Deep-dive from web_description (Layer C from your schema)
            data_types_compromised = extract_data_types_from_description(web_description)
            discovery_date = extract_discovery_date(web_description)
            credit_monitoring_offered, monitoring_duration = check_credit_monitoring(web_description)

            # Enhanced raw_data_json structure following your 3-tier schema
            raw_data = {
                # A. Portal row (direct from HTML table)
                "hhs_ocr_raw": {
                    "covered_entity_name": covered_entity_name,
                    "state": state,
                    "entity_type": entity_type,
                    "individuals_affected_raw": individuals_affected_raw,
                    "breach_submission_date": breach_submission_date_str,
                    "breach_type": breach_type,
                    "location_of_breached_info": location_breached_raw,
                    "business_associate_present": business_associate_present,
                    "web_description": web_description
                },

                # B. Derived/housekeeping (computed fields)
                "hhs_ocr_derived": {
                    "ocr_incident_uid": ocr_incident_uid,
                    "portal_status": "under_investigation",  # Default, could be enhanced
                    "portal_first_seen_utc": datetime.now().isoformat(),
                    "portal_last_seen_utc": datetime.now().isoformat(),
                    "is_repeat_listing": False,  # TODO: Implement duplicate detection
                    "breach_year": breach_year,
                    "location_breached_array": location_breached_array
                },

                # C. Deep-parse from web_description
                "hhs_ocr_analysis": {
                    "data_types_compromised": data_types_compromised,
                    "date_discovered": discovery_date,
                    "credit_monitoring_offered": credit_monitoring_offered,
                    "monitoring_duration_months": monitoring_duration,
                    "root_cause_keywords": [],  # TODO: Implement root cause extraction
                    "system_vectors": location_breached_array,  # Use parsed locations
                    "full_text_blob": web_description
                }
            }

            # Clean up the raw data (remove empty/null values)
            raw_data_json = {k: v for k, v in raw_data.items() if v is not None}

            # Generate unique URL using incident UID
            item_url = f"{HHS_OCR_BREACH_URL}#incident-{ocr_incident_uid}"

            # Create comprehensive summary
            summary_parts = []
            if breach_type:
                summary_parts.append(f"Type: {breach_type}")
            if location_breached_raw:
                summary_parts.append(f"Location: {location_breached_raw}")
            if individuals_affected:
                summary_parts.append(f"Affected: {individuals_affected:,} individuals")
            if business_associate_present.lower() == "yes":
                summary_parts.append("Business Associate involved")

            summary = ". ".join(summary_parts) + "." if summary_parts else "Healthcare data breach notification."

            # Enhanced tags
            tags = ["hhs_ocr", "healthcare_breach", "wall_of_shame"]
            if breach_type:
                tags.append(breach_type.lower().replace("/", "_").replace(" ", "_"))
            if business_associate_present.lower() == "yes":
                tags.append("business_associate_involved")
            if entity_type:
                tags.append(entity_type.lower().replace(" ", "_"))
            if state:
                tags.append(f"state_{state.lower()}")

            # Store ALL enhanced data in raw_data_json for future normalization
            enhanced_data = {
                # All the 3-tier data structure we extracted
                **raw_data_json,

                # Additional normalized fields for easy access and future database migration
                "normalized_fields": {
                    "data_types_compromised": data_types_compromised,
                    "incident_discovery_date": discovery_date,
                    "keywords_detected": tags,
                    "credit_monitoring_offered": credit_monitoring_offered,
                    "monitoring_duration_months": monitoring_duration,
                    "business_associate_involved": business_associate_present.lower() == "yes",
                    "entity_state": state,
                    "entity_type": entity_type,
                    "breach_type_category": breach_type,
                    "location_categories": location_breached_array,
                    "incident_containment_date": None,  # Placeholder for future extraction
                    "estimated_cost_min": None,  # Placeholder for future extraction
                    "estimated_cost_max": None,  # Placeholder for future extraction
                    "exhibit_urls": [item_url] if item_url else [],
                    "keyword_contexts": {
                        "breach_type": breach_type,
                        "location": location_breached_raw,
                        "entity_type": entity_type
                    }
                }
            }

            item_data = {
                "source_id": SOURCE_ID_HHS_OCR,
                "item_url": item_url,
                "title": covered_entity_name,
                "publication_date": publication_date_iso,
                "summary_text": summary.strip(),
                "full_content": web_description,
                "raw_data_json": enhanced_data,  # Contains ALL extracted data for future normalization
                "tags_keywords": list(set(tags)),

                # Map to basic existing schema fields (safe fields that should exist)
                "affected_individuals": individuals_affected,
                "breach_date": discovery_date.split('T')[0] if discovery_date else None,
                "reported_date": publication_date_iso.split('T')[0],
                "notice_document_url": item_url,
                # ALL advanced analysis is preserved in raw_data_json for future normalization
            }

            # TODO: Implement check for existing record before inserting to avoid duplicates.
            # This could be a query like:
            # exists = supabase_client.client.table("scraped_items") \
            # .select("id") \
            # .eq("title", name_of_covered_entity) \
            # .eq("publication_date", publication_date_iso) \
            # .eq("source_id", SOURCE_ID_HHS_OCR) \
            # .execute()
            # if not exists.data:
            #    insert_response = supabase_client.insert_item(**item_data) ...
            # else:
            #    logger.info(f"Item already exists for {name_of_covered_entity} on {publication_date_iso}. Skipping.")

            # Check for existing record before inserting
            try:
                query_result = supabase_client.client.table("scraped_items").select("id").eq("title", covered_entity_name).eq("publication_date", publication_date_iso).eq("source_id", SOURCE_ID_HHS_OCR).execute()
                if query_result.data:
                    logger.info(f"Item '{covered_entity_name}' on {publication_date_iso} already exists. Skipping.")
                    skipped_count += 1
                    continue
            except Exception as e_check:
                logger.warning(f"Could not check for existing record: {e_check}. Proceeding with insert.")

            try:
                insert_response = supabase_client.insert_item(**item_data)
                if insert_response:
                    logger.info(f"Successfully inserted item for '{covered_entity_name}'.")
                    inserted_count += 1
                else:
                    logger.error(f"Failed to insert item for '{covered_entity_name}'.")
            except Exception as e_insert:
                if "duplicate key value violates unique constraint" in str(e_insert):
                    logger.info(f"Item '{covered_entity_name}' already exists (duplicate URL). Skipping.")
                    skipped_count += 1
                else:
                    logger.error(f"Error inserting item for '{covered_entity_name}' into Supabase: {e_insert}")
                    skipped_count += 1

        except Exception as e:
            logger.error(f"Error processing row for '{covered_entity_name if 'covered_entity_name' in locals() else 'Unknown Entity'}': {e}", exc_info=True)
            skipped_count += 1

    logger.info(f"Finished processing HHS OCR breaches. Total rows processed: {processed_count}. Items inserted: {inserted_count}. Items skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("HHS OCR Breach Scraper Started")

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_hhs_ocr_breaches()

    logger.info("HHS OCR Breach Scraper Finished")
