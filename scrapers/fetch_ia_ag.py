import os
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from urllib.parse import urljoin
from dateutil import parser as dateutil_parser
import hashlib
import re
import io
import time

# Assuming SupabaseClient is in utils.supabase_client
try:
    from utils.supabase_client import SupabaseClient, clean_text_for_database
except ImportError:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from utils.supabase_client import SupabaseClient, clean_text_for_database

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
IOWA_AG_BASE_URL = "https://www.iowaattorneygeneral.gov/for-consumers/security-breach-notifications"


def _iowa_year_url(year: int) -> str:
    return f"{IOWA_AG_BASE_URL}/{year}-security-breach-notification/"


def _resolve_iowa_url() -> str:
    """
    Notification page for the current year.

    Iowa publishes one page per calendar year. Pinning the year meant the scraper kept reading a
    frozen archive and could never see current-year breaches.

    No network probe here: doing one at import makes the module slow and fragile to import, and
    a failed probe cannot distinguish "not published yet" from "temporarily unreachable" — so
    treating failure as absence would silently pin the scraper to last year. The fallback is
    applied against a real fetch instead; see _iowa_url_candidates().

    Override with IA_AG_YEAR for a backfill.
    """
    override = os.environ.get("IA_AG_YEAR", "").strip()
    if override.isdigit():
        return _iowa_year_url(int(override))
    return _iowa_year_url(datetime.now().year)


def _iowa_url_candidates() -> list:
    """Pages to try in order: current year, then the previous one for the early-January gap."""
    override = os.environ.get("IA_AG_YEAR", "").strip()
    if override.isdigit():
        return [_iowa_year_url(int(override))]

    this_year = datetime.now().year
    return [_iowa_year_url(this_year), _iowa_year_url(this_year - 1)]


IOWA_AG_2025_URL = _resolve_iowa_url()
SOURCE_ID_IOWA_AG = 8

# Configuration from environment variables
FILTER_FROM_DATE = os.environ.get("IA_AG_FILTER_FROM_DATE")  # Format: "YYYY-MM-DD"
PROCESSING_MODE = os.environ.get("IA_AG_PROCESSING_MODE", "ENHANCED")  # BASIC, ENHANCED, FULL

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Rate limiting
RATE_LIMIT_DELAY = 2  # seconds between requests

def rate_limit_delay():
    """Add delay between requests to be respectful to the server."""
    time.sleep(RATE_LIMIT_DELAY)

def parse_date_flexible_ia(date_str: str) -> str | None:
    """
    Parse Iowa AG date strings (format: M-D-YYYY) to ISO 8601 format.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided', 'ongoing']:
        return None
    try:
        # Iowa AG uses M-D-YYYY format (e.g., "1-7-2025", "1-16-2025")
        dt_object = dateutil_parser.parse(date_str.strip())
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse Iowa AG date string: '{date_str}'. Error: {e}")
        return None

def parse_date_to_date_only(date_str: str) -> str | None:
    """
    Parse date string and return only the date part (YYYY-MM-DD).
    """
    if not date_str:
        return None
    try:
        dt_object = dateutil_parser.parse(date_str.strip())
        return dt_object.date().isoformat()
    except (ValueError, TypeError, OverflowError):
        return None

def generate_incident_uid_ia(organization_name: str, reported_date: str) -> str:
    """
    Generate a unique incident identifier for Iowa AG breaches.
    Format: IA_AG_2025_{hash}
    """
    # Create a unique string from organization name and date
    unique_string = f"iowa_ag_2025_{organization_name.lower().strip()}_{reported_date}"
    # Generate a short hash
    hash_object = hashlib.md5(unique_string.encode())
    short_hash = hash_object.hexdigest()[:8]
    return f"IA_AG_2025_{short_hash.upper()}"

def should_process_record_ia(reported_date_str: str) -> bool:
    """
    Determine if a breach record should be processed based on date filtering.
    """
    if not FILTER_FROM_DATE:
        return True

    try:
        filter_date = datetime.strptime(FILTER_FROM_DATE, "%Y-%m-%d").date()

        # Parse the reported date
        parsed_date = parse_date_to_date_only(reported_date_str)
        if parsed_date:
            record_date = datetime.strptime(parsed_date, "%Y-%m-%d").date()
            return record_date >= filter_date

        # If no valid date found, include the record
        return True

    except Exception as e:
        logger.warning(f"Error in date filtering: {e}")
        return True

def extract_affected_individuals_ia(text: str) -> int | None:
    """
    Extract number of affected individuals from text using regex patterns.
    """
    if not text:
        return None

    # Common patterns for affected individuals
    patterns = [
        r'(\d{1,3}(?:,\d{3})*)\s*(?:individuals?|people|persons?|residents?|customers?|patients?|members?)',
        r'(?:affecting|affected|impacted)\s*(\d{1,3}(?:,\d{3})*)',
        r'(\d{1,3}(?:,\d{3})*)\s*(?:iowa\s*)?(?:residents?|individuals?)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text.lower())
        if matches:
            try:
                # Remove commas and convert to int
                number_str = matches[0].replace(',', '')
                return int(number_str)
            except (ValueError, IndexError):
                continue

    return None

def analyze_pdf_content_ia(pdf_url: str) -> dict:
    """
    Enhanced PDF content analysis for comprehensive breach details (Tier 3).
    Extracts affected individuals, data types, and incident details from Iowa AG PDFs.
    """
    try:
        logger.info(f"Analyzing Iowa AG PDF: {pdf_url}")

        pdf_analysis = {
            'pdf_analyzed': True,
            'pdf_url': pdf_url,
            'affected_individuals': None,
            'what_information_involved': {},
            'raw_text': '',
            'extraction_confidence': 'low'  # Track confidence in extraction
        }

        # Add rate limiting delay before PDF request
        rate_limit_delay()

        # Extract PDF content using local libraries (PyPDF2 and pdfplumber)
        try:
            response = requests.get(pdf_url, headers=REQUEST_HEADERS, timeout=30)
            response.raise_for_status()

            if response.status_code == 200:
                # Try PyPDF2 first
                try:
                    import PyPDF2
                    pdf_file = io.BytesIO(response.content)
                    pdf_reader = PyPDF2.PdfReader(pdf_file)

                    text_content = ""
                    for page in pdf_reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_content += page_text + "\n"

                    if text_content.strip():
                        # Clean the extracted text to prevent Unicode errors in database
                        text_content = clean_text_for_database(text_content)
                        content = text_content.lower()
                        pdf_analysis['raw_text'] = text_content[:1000]  # Store sample
                        pdf_analysis['extraction_confidence'] = 'high'
                        logger.debug(f"PyPDF2 extraction successful for {pdf_url}")
                    else:
                        raise Exception("No text extracted from PDF with PyPDF2")

                except ImportError:
                    logger.debug("PyPDF2 not available, trying pdfplumber")
                    raise Exception("PyPDF2 not available")

                except Exception as pypdf_error:
                    logger.debug(f"PyPDF2 extraction failed: {pypdf_error}, trying pdfplumber")

                    # Try pdfplumber as alternative
                    try:
                        import pdfplumber
                        pdf_file = io.BytesIO(response.content)

                        text_content = ""
                        with pdfplumber.open(pdf_file) as pdf:
                            for page in pdf.pages:
                                page_text = page.extract_text()
                                if page_text:
                                    text_content += page_text + "\n"

                        if text_content.strip():
                            # Clean the extracted text to prevent Unicode errors in database
                            text_content = clean_text_for_database(text_content)
                            content = text_content.lower()
                            pdf_analysis['raw_text'] = text_content[:1000]  # Store sample
                            pdf_analysis['extraction_confidence'] = 'high'
                            logger.debug(f"pdfplumber extraction successful for {pdf_url}")
                        else:
                            raise Exception("No text extracted from PDF with pdfplumber")

                    except ImportError:
                        logger.warning("Neither PyPDF2 nor pdfplumber available for PDF extraction")
                        pdf_analysis['extraction_confidence'] = 'failed'
                        return pdf_analysis

                    except Exception as pdfplumber_error:
                        logger.warning(f"Both PyPDF2 and pdfplumber failed for {pdf_url}: {pdfplumber_error}")
                        pdf_analysis['extraction_confidence'] = 'failed'
                        return pdf_analysis

                # Extract affected individuals
                affected_individuals = extract_affected_individuals_ia(text_content)
                if affected_individuals:
                    pdf_analysis['affected_individuals'] = affected_individuals

                # Extract "what information was involved" section
                what_info_patterns = [
                    r'what\s+(?:information|data)\s+(?:was\s+)?(?:involved|affected|compromised|accessed|disclosed)',
                    r'types?\s+of\s+(?:information|data)\s+(?:involved|affected|compromised)',
                    r'personal\s+information\s+(?:involved|affected|compromised)',
                    r'information\s+(?:that\s+)?(?:may\s+have\s+been\s+)?(?:involved|affected|compromised|accessed)'
                ]

                for pattern in what_info_patterns:
                    match = re.search(pattern, content)
                    if match:
                        # Extract text after the pattern (next 500 characters)
                        start_pos = match.end()
                        extracted_text = text_content[start_pos:start_pos + 500].strip()
                        if extracted_text:
                            pdf_analysis['what_information_involved']['text'] = extracted_text
                            break

                logger.info(f"Successfully analyzed PDF: {pdf_url}")

        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to download PDF {pdf_url}: {e}")
            pdf_analysis['extraction_confidence'] = 'failed'

        except Exception as e:
            logger.warning(f"Error analyzing PDF {pdf_url}: {e}")
            pdf_analysis['extraction_confidence'] = 'failed'

        return pdf_analysis

    except Exception as e:
        logger.error(f"Critical error in PDF analysis for {pdf_url}: {e}")
        return {
            'pdf_analyzed': False,
            'pdf_url': pdf_url,
            'error': str(e),
            'extraction_confidence': 'failed'
        }

def process_iowa_ag_breaches_2025():
    """
    Enhanced Iowa AG 2025 Security Breach Notification processing with 3-tier data structure.
    Processes the 2025 page specifically with comprehensive field mapping and PDF analysis.
    """
    logger.info("Starting Enhanced Iowa AG 2025 Security Breach Notification processing...")

    # Filter configuration
    if FILTER_FROM_DATE:
        try:
            filter_date = datetime.strptime(FILTER_FROM_DATE, '%Y-%m-%d').date()
            logger.info(f"Date filtering enabled: collecting breaches from {filter_date} onward")
        except ValueError:
            logger.warning(f"Invalid FILTER_FROM_DATE format '{FILTER_FROM_DATE}', using one week back")
            filter_date = (date.today() - timedelta(days=7))
    else:
        filter_date = None
        logger.info("Testing mode: collecting ALL 2025 breach data (no date filtering)")

    # Try the current year's page, falling back to the previous year only when the current one
    # cannot be fetched. The fallback is driven by a real request rather than an import-time
    # probe, so a transient failure cannot silently pin the scraper to a stale year.
    global IOWA_AG_2025_URL

    response = None
    for candidate_url in _iowa_url_candidates():
        try:
            candidate_response = requests.get(candidate_url, headers=REQUEST_HEADERS, timeout=30)
            candidate_response.raise_for_status()
            response = candidate_response
            IOWA_AG_2025_URL = candidate_url
            logger.info(f"Using Iowa AG notification page: {candidate_url}")
            break
        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not fetch {candidate_url}: {e}")

    if response is None:
        logger.error("Could not fetch any Iowa AG notification page; aborting")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Iowa AG 2025 site structure: Simple table with two columns
    # Find the main table containing breach notifications
    main_table = soup.find('table')

    if not main_table:
        logger.error("Could not find main table for 2025 breach notifications. Page structure might have changed.")
        logger.debug(f"Page content sample (first 1000 chars): {response.text[:1000]}")
        return

    logger.info("Found main table for 2025 breach notifications.")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    inserted_count = 0
    processed_count = 0
    skipped_count = 0

    # Extract table rows (skip header row)
    tbody = main_table.find('tbody')
    if not tbody:
        # Some tables might just have <tr> directly under <table>
        table_rows = main_table.find_all('tr')
        # Remove header row if present (first <tr> with <th>)
        if table_rows and table_rows[0].find_all('th'):
            table_rows = table_rows[1:]
    else:
        table_rows = tbody.find_all('tr')

    if not table_rows:
        logger.info("No breach notification rows found in 2025 table.")
        return

    logger.info(f"Found {len(table_rows)} potential breach notifications in 2025 table.")

    # Process each table row
    for row_idx, row in enumerate(table_rows):
        processed_count += 1
        cols = row.find_all('td')

        if len(cols) < 2:  # Need at least Date Reported and Organization Name
            logger.warning(f"Skipping row {row_idx+1} due to insufficient columns ({len(cols)}). Content: {[c.get_text(strip=True)[:30] for c in cols]}")
            skipped_count += 1
            continue

        try:
            # Extract basic data from table columns
            # Column 0: Date Reported
            # Column 1: Organization Name (with PDF links)
            date_reported_str = cols[0].get_text(strip=True)
            organization_cell = cols[1]  # Cell contains organization name and PDF links

            # Extract organization name (clean text without links)
            organization_name = organization_cell.get_text(strip=True)

            # Extract all PDF links from the organization cell
            pdf_links = []
            supplemental_links = []

            for link_tag in organization_cell.find_all('a', href=True):
                link_url = urljoin(IOWA_AG_2025_URL, link_tag['href'])
                link_text = link_tag.get_text(strip=True)

                if 'supplemental' in link_text.lower():
                    supplemental_links.append({
                        'url': link_url,
                        'text': link_text,
                        'type': 'supplemental'
                    })
                else:
                    pdf_links.append({
                        'url': link_url,
                        'text': link_text,
                        'type': 'primary'
                    })

            # Get primary PDF URL (first non-supplemental link)
            primary_pdf_url = pdf_links[0]['url'] if pdf_links else None

            # Clean organization name - remove supplemental text and dates
            # Extract just the company name before any comma or supplemental info
            if ',' in organization_name:
                organization_name = organization_name.split(',')[0].strip()

            # Skip if we don't have essential data
            if not organization_name or not date_reported_str or not primary_pdf_url:
                logger.warning(f"Skipping row {row_idx+1} due to missing essential data: org='{organization_name}', date='{date_reported_str}', pdf='{primary_pdf_url}'")
                skipped_count += 1
                continue

            # Apply date filtering
            if not should_process_record_ia(date_reported_str):
                logger.info(f"Skipping '{organization_name}' - reported date {date_reported_str} is before filter date")
                skipped_count += 1
                continue

            # Parse dates
            publication_date_iso = parse_date_flexible_ia(date_reported_str)
            if not publication_date_iso:
                logger.warning(f"Skipping '{organization_name}' due to unparsable reported date: '{date_reported_str}'")
                skipped_count += 1
                continue

            reported_date_only = parse_date_to_date_only(date_reported_str)

            # Generate incident UID for deduplication
            incident_uid = generate_incident_uid_ia(organization_name, reported_date_only or date_reported_str)

            # Check if item already exists
            unique_url = f"{IOWA_AG_2025_URL}#{incident_uid}"
            if supabase_client.check_item_exists(unique_url):
                logger.info(f"Item already exists for '{organization_name}' on {date_reported_str}. Skipping.")
                skipped_count += 1
                continue

            # Build 3-tier data structure
            raw_data = {
                # Tier 1: Portal Data (Raw extraction from table)
                "tier_1_portal_data": {
                    "source_url": IOWA_AG_2025_URL,
                    "extraction_timestamp": datetime.now().isoformat(),
                    "table_row_index": row_idx,
                    "raw_date_reported": date_reported_str,
                    "raw_organization_name": organization_name,
                    "primary_pdf_url": primary_pdf_url,
                    "all_pdf_links": pdf_links,
                    "supplemental_links": supplemental_links,
                    "processing_mode": PROCESSING_MODE
                },

                # Tier 2: Derived/enrichment (computed fields)
                "tier_2_enhanced": {
                    "incident_uid": incident_uid,
                    "portal_first_seen_utc": datetime.now().isoformat(),
                    "portal_last_seen_utc": datetime.now().isoformat(),
                    "has_supplemental_documents": len(supplemental_links) > 0,
                    "total_documents": len(pdf_links) + len(supplemental_links),
                    "enhancement_attempted": False,
                    "enhancement_errors": []
                },

                # Tier 3: Deep-dive from PDF (placeholder for PDF analysis)
                "tier_3_pdf_analysis": []
            }

            # Initialize variables for enhanced data
            affected_individuals = None
            what_was_leaked_value = None

            # Perform PDF analysis based on processing mode
            if PROCESSING_MODE in ["ENHANCED", "FULL"] and primary_pdf_url:
                try:
                    pdf_analysis = analyze_pdf_content_ia(primary_pdf_url)
                    raw_data["tier_3_pdf_analysis"].append(pdf_analysis)
                    raw_data["tier_2_enhanced"]["enhancement_attempted"] = True

                    # Extract enhanced data from PDF analysis
                    if pdf_analysis.get('affected_individuals'):
                        affected_individuals = pdf_analysis['affected_individuals']

                    # Extract what information was involved
                    what_info = pdf_analysis.get('what_information_involved', {})
                    if what_info.get('text'):
                        what_was_leaked_value = what_info['text']
                    else:
                        # Fallback to PDF URL if no text extracted
                        what_was_leaked_value = primary_pdf_url

                except Exception as e:
                    logger.warning(f"PDF analysis failed for '{organization_name}': {e}")
                    raw_data["tier_2_enhanced"]["enhancement_errors"].append(f"PDF analysis failed: {str(e)}")
                    what_was_leaked_value = primary_pdf_url  # Fallback to PDF URL
            else:
                # In BASIC mode, just use PDF URL as fallback
                what_was_leaked_value = primary_pdf_url

            # Build summary
            summary = f"Security breach notification for {organization_name} reported to Iowa AG on {date_reported_str}."
            if len(supplemental_links) > 0:
                summary += f" Includes {len(supplemental_links)} supplemental document(s)."

            # Build full content
            full_content = f"Organization: {organization_name}\n"
            full_content += f"Date Reported to Iowa AG: {date_reported_str}\n"
            full_content += f"Primary Document: {primary_pdf_url}\n"
            if supplemental_links:
                full_content += f"Supplemental Documents: {len(supplemental_links)}\n"
                for supp in supplemental_links:
                    full_content += f"  - {supp['text']}: {supp['url']}\n"

            # Prepare database item
            db_item = {
                'source_id': SOURCE_ID_IOWA_AG,
                'item_url': unique_url,
                'title': organization_name,
                'publication_date': publication_date_iso,
                'summary_text': summary,
                'full_content': full_content,
                'reported_date': reported_date_only,
                'affected_individuals': affected_individuals,
                'notice_document_url': primary_pdf_url,
                'what_was_leaked': what_was_leaked_value,
                'tags_keywords': ["iowa_ag", "ia_breach", "2025"],
                'raw_data_json': {
                    'scraper_version': '1.0_enhanced_iowa_ag_2025',
                    **raw_data
                }
            }

            # Insert into database
            insert_response = supabase_client.insert_item(**db_item)
            if insert_response:
                logger.info(f"Successfully inserted item for '{organization_name}' reported on {date_reported_str}. URL: {unique_url}")
                inserted_count += 1
            else:
                logger.error(f"Failed to insert item for '{organization_name}' reported on {date_reported_str}")

        except Exception as e:
            logger.error(f"Error processing row for '{organization_name if 'organization_name' in locals() else 'Unknown Organization'}': {row.text[:150]}. Error: {e}", exc_info=True)
            skipped_count += 1

    logger.info(f"Finished processing Iowa AG breaches. Total items processed: {processed_count}. Items inserted: {inserted_count}. Items skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("Enhanced Iowa AG 2025 Security Breach Scraper Started")

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        logger.info(f"Processing mode: {PROCESSING_MODE}")
        if FILTER_FROM_DATE:
            logger.info(f"Date filtering enabled from: {FILTER_FROM_DATE}")
        else:
            logger.info("Date filtering disabled - collecting all 2025 data")

        process_iowa_ag_breaches_2025()

    logger.info("Enhanced Iowa AG 2025 Security Breach Scraper Finished")
