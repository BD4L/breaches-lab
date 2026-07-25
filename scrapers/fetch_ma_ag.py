import os
import sys
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

from dateutil import parser as dateutil_parser
import re
import hashlib
import PyPDF2
import pdfplumber
from io import BytesIO

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
MASSACHUSETTS_AG_BASE_URL = "https://www.mass.gov"
MASSACHUSETTS_AG_SUMMARY_URL = "https://www.mass.gov/lists/data-breach-notification-reports"
MASSACHUSETTS_AG_2025_PDF_URL = "https://www.mass.gov/doc/data-breach-report-2025/download"
SOURCE_ID_MASSACHUSETTS_AG = 11

# Environment variables for configuration
MA_AG_PROCESSING_MODE = os.environ.get("MA_AG_PROCESSING_MODE", "ENHANCED")  # BASIC, ENHANCED, or FULL
MA_AG_STATE_FILE = os.environ.get("MA_AG_STATE_FILE", "ma_ag_state.json")  # File to track changes
MA_AG_FILTER_DAYS_BACK = int(os.environ.get("MA_AG_FILTER_DAYS_BACK", "7"))  # Only process breaches from last N days
MA_AG_FORCE_PROCESS = os.environ.get("MA_AG_FORCE_PROCESS", "false").lower() == "true"  # Skip change detection

# Browser-like headers to avoid WAF blocking
COMMON_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/125.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive",
    "DNT": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0"
}

# Global session for cookie persistence
_session = None

def get_session():
    """
    Get or create a persistent session with proper headers.
    """
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(COMMON_HEADERS)
        logger.info("Created new session with browser-like headers")
    return _session

def get_direct_download_response(mass_gov_url):
    """
    Try to download directly from mass.gov URL.
    Some URLs serve content directly (200) instead of redirecting to S3.
    """
    import urllib.parse as urlparse

    try:
        logger.info(f"Attempting direct download from: {mass_gov_url}")

        # Make request without following redirects first to check
        response = requests.get(mass_gov_url, allow_redirects=False, timeout=15)

        if response.is_redirect:
            s3_location = response.headers.get("location")
            if s3_location:
                # Handle relative URLs
                if s3_location.startswith("/"):
                    s3_url = urlparse.urljoin("https://www.mass.gov", s3_location)
                else:
                    s3_url = s3_location

                logger.info(f"Found S3 redirect URL: {s3_url}")
                # Download from S3 directly
                return download_from_s3_direct(s3_url)
            else:
                logger.warning("Redirect response but no location header found")
                return None
        elif response.status_code == 200:
            # Content served directly - download it
            logger.info(f"Content served directly (status: {response.status_code})")
            # Get the full content
            full_response = requests.get(mass_gov_url, timeout=60)
            full_response.raise_for_status()
            logger.info(f"Successfully downloaded directly: {len(full_response.content)} bytes")
            return full_response
        else:
            logger.warning(f"Unexpected status: {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Failed to download from mass.gov URL: {e}")
        return None

def download_from_s3_direct(s3_url, max_retries=3):
    """
    Download file directly from S3 URL, bypassing mass.gov WAF.
    """
    import time

    for attempt in range(max_retries):
        try:
            logger.info(f"Downloading from S3 directly (attempt {attempt + 1}/{max_retries}): {s3_url}")

            if attempt > 0:
                time.sleep(2 * attempt)  # Progressive delay

            # Direct request to S3 - no special headers needed
            response = requests.get(s3_url, timeout=60, stream=True)
            response.raise_for_status()

            logger.info(f"Successfully downloaded from S3 (status: {response.status_code}, size: {len(response.content)} bytes)")
            return response

        except Exception as e:
            logger.error(f"S3 download attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise

    return None

def make_request_with_s3_fallback(url, max_retries=3, delay=2, extra_headers=None):
    """
    Make HTTP request with S3 fallback for mass.gov URLs.
    First tries the S3 redirect approach, then falls back to direct request.
    """
    import time
    import random

    # For mass.gov download URLs, try direct download first
    if "mass.gov" in url and ("/doc/" in url or "/download" in url):
        logger.info("Detected mass.gov download URL - trying direct download approach")

        try:
            direct_response = get_direct_download_response(url)
            if direct_response:
                return direct_response
            else:
                logger.warning("Direct download approach failed, falling back to session request")
        except Exception as e:
            logger.warning(f"Direct download approach failed: {e}, falling back to session request")

    # Fallback to direct request (original approach)
    session = get_session()

    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting direct fetch {url} (attempt {attempt + 1}/{max_retries})")

            # Random delay to avoid looking like a bot
            if attempt > 0:
                wait_time = delay * attempt + random.uniform(1, 3)
                logger.info(f"Waiting {wait_time:.1f} seconds before retry...")
                time.sleep(wait_time)
            else:
                time.sleep(random.uniform(1, 2))

            # Prepare headers for this request
            request_headers = {}
            if extra_headers:
                request_headers.update(extra_headers)

            response = session.get(url, headers=request_headers, timeout=30)
            response.raise_for_status()

            logger.info(f"Successfully fetched {url} (status: {response.status_code})")
            return response

        except requests.exceptions.HTTPError as e:
            if hasattr(e, 'response') and e.response.status_code == 403:
                logger.warning(f"403 Forbidden error on attempt {attempt + 1}. WAF blocking request.")
                if attempt < max_retries - 1:
                    logger.info("Will retry with longer delay...")
                else:
                    logger.error(f"All {max_retries} attempts failed with 403 Forbidden.")
                    raise
            else:
                logger.error(f"HTTP error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                raise

    return None

def initialize_session_with_landing_page():
    """
    Initialize session by visiting the base domain first, then the landing page.
    This mimics real browser behavior to bypass mass.gov's WAF.
    """
    import time
    import random

    logger.info("Initializing session with multi-step approach...")
    session = get_session()

    try:
        # Step 1: Visit base domain first to establish initial session
        logger.info("Step 1: Visiting base domain...")
        base_response = session.get("https://www.mass.gov", timeout=15)
        base_response.raise_for_status()
        logger.info(f"Base domain visit successful (status: {base_response.status_code})")
        logger.info(f"Initial cookies: {list(session.cookies.keys())}")

        # Wait like a real user
        time.sleep(random.uniform(3, 6))

        # Step 2: Visit a general page to look more human
        logger.info("Step 2: Visiting general page...")
        general_response = session.get("https://www.mass.gov/orgs/office-of-the-attorney-general", timeout=15)
        general_response.raise_for_status()
        logger.info(f"General page visit successful (status: {general_response.status_code})")

        # Wait again
        time.sleep(random.uniform(2, 5))

        # Step 3: Now visit the target landing page
        logger.info("Step 3: Visiting breach notification landing page...")
        target_response = session.get(MASSACHUSETTS_AG_SUMMARY_URL, timeout=15)
        target_response.raise_for_status()

        logger.info(f"Successfully visited landing page (status: {target_response.status_code})")
        logger.info(f"Final session cookies: {list(session.cookies.keys())}")

        # Final wait before making additional requests
        time.sleep(random.uniform(2, 4))
        return True

    except Exception as e:
        logger.error(f"Failed to initialize session: {e}")

        # Try a simpler approach as fallback
        logger.info("Trying simpler fallback approach...")
        try:
            # Just try the target page directly with more realistic headers
            fallback_headers = {
                "Referer": "https://www.mass.gov/",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Dest": "document"
            }

            fallback_response = session.get(MASSACHUSETTS_AG_SUMMARY_URL,
                                          headers=fallback_headers, timeout=15)
            fallback_response.raise_for_status()

            logger.info(f"Fallback approach successful (status: {fallback_response.status_code})")
            return True

        except Exception as e2:
            logger.error(f"Fallback approach also failed: {e2}")
            return False

def parse_date_flexible_ma(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided', 'ongoing', 'see letter', '']:
        return None
    try:
        # mass.gov uses "Month Day, Year" e.g. "January 1, 2023"
        dt_object = dateutil_parser.parse(date_str.strip())
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def is_breach_recent(date_reported_str: str, days_back: int = 7) -> bool:
    """
    Check if a breach was reported within the last N days.
    Returns True if recent, False if older or unparseable.
    """
    if not date_reported_str:
        return False

    try:
        # Parse the reported date
        reported_date = dateutil_parser.parse(date_reported_str.strip())

        # Calculate cutoff date (N days ago)
        cutoff_date = datetime.now() - timedelta(days=days_back)

        # Check if breach is recent
        is_recent = reported_date.date() >= cutoff_date.date()

        if is_recent:
            logger.info(f"Recent breach found: reported {reported_date.strftime('%Y-%m-%d')} (within last {days_back} days)")
        else:
            logger.debug(f"Older breach skipped: reported {reported_date.strftime('%Y-%m-%d')} (older than {days_back} days)")

        return is_recent

    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date for recency check: '{date_reported_str}'. Error: {e}")
        return False

def load_state_file():
    """
    Load the state file that tracks PDF changes.
    Returns dict with previous state or empty dict if file doesn't exist.
    """
    import json

    try:
        if os.path.exists(MA_AG_STATE_FILE):
            with open(MA_AG_STATE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load state file {MA_AG_STATE_FILE}: {e}")

    return {}

def save_state_file(state_data):
    """
    Save the current state to file.
    """
    import json

    try:
        with open(MA_AG_STATE_FILE, 'w') as f:
            json.dump(state_data, f, indent=2)
        logger.info(f"Saved state to {MA_AG_STATE_FILE}")
    except Exception as e:
        logger.error(f"Could not save state file {MA_AG_STATE_FILE}: {e}")

def get_summary_page_info():
    """
    Get current breach count and PDF info from the summary page.
    Returns dict with current state or None if failed.
    """
    try:
        logger.info("Fetching Massachusetts AG summary page...")
        response = make_request_with_s3_fallback(MASSACHUSETTS_AG_SUMMARY_URL)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract 2025 breach count from the table
        breach_count_2025 = None
        affected_count_2025 = None

        # Find the table with breach statistics
        for row in soup.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) >= 3:
                year_cell = cells[0].get_text(strip=True)
                if year_cell == "2025":
                    breach_count_2025 = cells[1].get_text(strip=True).replace(',', '')
                    affected_count_2025 = cells[2].get_text(strip=True).replace(',', '')
                    break

        # Extract PDF size from the download link
        pdf_size_kb = None
        for link in soup.find_all('a', href=True):
            if 'data-breach-report-2025' in link.get('href', ''):
                link_text = link.get_text(strip=True)
                # Extract size like "840.1 KB"
                size_match = re.search(r'(\d+(?:\.\d+)?)\s*KB', link_text)
                if size_match:
                    pdf_size_kb = float(size_match.group(1))
                break

        current_state = {
            "breach_count_2025": int(breach_count_2025) if breach_count_2025 and breach_count_2025.isdigit() else None,
            "affected_count_2025": int(affected_count_2025) if affected_count_2025 and affected_count_2025.isdigit() else None,
            "pdf_size_kb": pdf_size_kb,
            "last_checked": datetime.now().isoformat(),
            "pdf_url": MASSACHUSETTS_AG_2025_PDF_URL
        }

        logger.info(f"Current state: {breach_count_2025} breaches, {affected_count_2025} affected, PDF size: {pdf_size_kb} KB")
        return current_state

    except Exception as e:
        logger.error(f"Failed to get summary page info: {e}")
        return None

def has_data_changed(current_state, previous_state):
    """
    Check if the data has changed since last run.
    Returns True if changes detected, False otherwise.
    """
    if not previous_state:
        logger.info("No previous state found - will process PDF")
        return True

    changes = []

    # Check breach count
    if current_state.get("breach_count_2025") != previous_state.get("breach_count_2025"):
        changes.append(f"Breach count: {previous_state.get('breach_count_2025')} {current_state.get('breach_count_2025')}")

    # Check affected count
    if current_state.get("affected_count_2025") != previous_state.get("affected_count_2025"):
        changes.append(f"Affected count: {previous_state.get('affected_count_2025')} {current_state.get('affected_count_2025')}")

    # Check PDF size
    if current_state.get("pdf_size_kb") != previous_state.get("pdf_size_kb"):
        changes.append(f"PDF size: {previous_state.get('pdf_size_kb')} KB {current_state.get('pdf_size_kb')} KB")

    if changes:
        logger.info(f"Changes detected: {'; '.join(changes)}")
        return True
    else:
        logger.info("No changes detected - skipping PDF processing")
        return False

def create_incident_uid(org_name: str, pdf_url: str) -> str:
    """
    Create a unique identifier for the breach incident.
    """
    combined_string = f"{org_name}_{pdf_url}"
    return hashlib.md5(combined_string.encode()).hexdigest()

def parse_annual_pdf_content(pdf_url: str) -> list:
    """
    Parse the annual Massachusetts AG PDF report.
    Returns list of breach records with structured data.

    Expected PDF structure:
    Breach Number | Date Reported To OCA | Reporting Organization Name |
    Reporting Organization Type | MA Residents Affected | SSN Breached |
    Medical Records Breached | Financial Account Breached |
    Drivers Licenses Breached | Credit/Debit Numbers Breached
    """
    breach_records = []

    try:
        logger.info(f"Downloading and parsing annual PDF: {pdf_url}")
        # Use referer header for PDF download
        extra_headers = {"Referer": MASSACHUSETTS_AG_SUMMARY_URL}
        response = make_request_with_s3_fallback(pdf_url, max_retries=2, delay=3, extra_headers=extra_headers)
        if not response:
            logger.error("Failed to download annual PDF after retries")
            return breach_records

        pdf_size_bytes = len(response.content)
        logger.info(f"Downloaded PDF: {pdf_size_bytes} bytes")

        # Try pdfplumber first (better for table extraction)
        try:
            with pdfplumber.open(BytesIO(response.content)) as pdf:
                logger.info(f"PDF has {len(pdf.pages)} pages")

                for page_num, page in enumerate(pdf.pages):
                    logger.info(f"Processing page {page_num + 1}")

                    # Extract tables from the page
                    tables = page.extract_tables()

                    for table_num, table in enumerate(tables):
                        if not table:
                            continue

                        logger.info(f"Found table {table_num + 1} with {len(table)} rows")

                        # Find header row (contains "Breach Number", "Date Reported", etc.)
                        header_row_idx = None
                        for i, row in enumerate(table):
                            if row and any(cell and "Breach" in str(cell) and "Number" in str(cell) for cell in row):
                                header_row_idx = i
                                break

                        if header_row_idx is None:
                            continue

                        headers = table[header_row_idx]
                        logger.info(f"Found headers: {headers}")

                        # Process data rows
                        for row_idx in range(header_row_idx + 1, len(table)):
                            row = table[row_idx]
                            if not row or not any(row):  # Skip empty rows
                                continue

                            # Skip rows that don't start with "2025-" (breach number)
                            if not row[0] or not str(row[0]).strip().startswith("2025-"):
                                continue

                            try:
                                # Map row data to structured format
                                breach_record = {
                                    "breach_number": str(row[0]).strip() if row[0] else "",
                                    "date_reported": str(row[1]).strip() if len(row) > 1 and row[1] else "",
                                    "organization_name": str(row[2]).strip() if len(row) > 2 and row[2] else "",
                                    "organization_type": str(row[3]).strip() if len(row) > 3 and row[3] else "",
                                    "ma_residents_affected": str(row[4]).strip() if len(row) > 4 and row[4] else "",
                                    "ssn_breached": str(row[5]).strip() if len(row) > 5 and row[5] else "",
                                    "medical_records_breached": str(row[6]).strip() if len(row) > 6 and row[6] else "",
                                    "financial_account_breached": str(row[7]).strip() if len(row) > 7 and row[7] else "",
                                    "drivers_licenses_breached": str(row[8]).strip() if len(row) > 8 and row[8] else "",
                                    "credit_debit_breached": str(row[9]).strip() if len(row) > 9 and row[9] else "",
                                    "pdf_page": page_num + 1,
                                    "pdf_table": table_num + 1,
                                    "pdf_size_bytes": pdf_size_bytes
                                }

                                breach_records.append(breach_record)
                                logger.info(f"Parsed breach: {breach_record['breach_number']} - {breach_record['organization_name']}")

                            except Exception as e:
                                logger.warning(f"Error parsing row {row_idx}: {e}")
                                continue

                logger.info(f"Successfully parsed {len(breach_records)} breach records from PDF")

        except Exception as e:
            logger.error(f"pdfplumber failed for annual PDF: {e}")
            # Could add PyPDF2 fallback here if needed

    except Exception as e:
        logger.error(f"Failed to process annual PDF {pdf_url}: {e}")

    return breach_records

def extract_pdf_content(pdf_url: str) -> dict:
    """
    Extract content from PDF breach notification.
    Returns dict with extracted information.
    """
    pdf_data = {
        "pdf_processed": False,
        "pdf_size_bytes": None,
        "affected_individuals_text": None,
        "breach_date_text": None,
        "what_was_leaked": None,
        "pdf_text_preview": None,
        "extraction_error": None
    }

    try:
        logger.info(f"Downloading PDF: {pdf_url}")
        extra_headers = {"Referer": MASSACHUSETTS_AG_SUMMARY_URL}
        response = make_request_with_s3_fallback(pdf_url, max_retries=2, delay=1, extra_headers=extra_headers)
        if not response:
            pdf_data["extraction_error"] = "Failed to download PDF after retries"
            return pdf_data

        pdf_data["pdf_size_bytes"] = len(response.content)

        # Try pdfplumber first (better for text extraction)
        try:
            with pdfplumber.open(BytesIO(response.content)) as pdf:
                full_text = ""
                for page in pdf.pages[:5]:  # Limit to first 5 pages
                    page_text = page.extract_text()
                    if page_text:
                        full_text += page_text + "\n"

                if full_text.strip():
                    pdf_data["pdf_text_preview"] = full_text[:1000]  # First 1000 chars

                    # Extract affected individuals count
                    affected_patterns = [
                        r'(\d{1,3}(?:,\d{3})*)\s+(?:Massachusetts\s+)?(?:residents?|individuals?|people|persons?)',
                        r'(?:approximately|about|roughly)\s+(\d{1,3}(?:,\d{3})*)\s+(?:Massachusetts\s+)?(?:residents?|individuals?)',
                        r'(\d{1,3}(?:,\d{3})*)\s+(?:MA|Mass\.?)\s+(?:residents?|individuals?)',
                        r'total\s+of\s+(\d{1,3}(?:,\d{3})*)\s+(?:individuals?|people|persons?)'
                    ]

                    for pattern in affected_patterns:
                        match = re.search(pattern, full_text, re.IGNORECASE)
                        if match:
                            pdf_data["affected_individuals_text"] = match.group(0)
                            break

                    # Extract breach date
                    breach_date_patterns = [
                        r'(?:incident|breach|attack|unauthorized access).*?(?:occurred|discovered|detected).*?(\w+\s+\d{1,2},?\s+\d{4})',
                        r'(?:on|around)\s+(\w+\s+\d{1,2},?\s+\d{4}).*?(?:incident|breach|attack)',
                        r'(\w+\s+\d{1,2},?\s+\d{4}).*?(?:incident|breach|attack|unauthorized)'
                    ]

                    for pattern in breach_date_patterns:
                        match = re.search(pattern, full_text, re.IGNORECASE)
                        if match:
                            pdf_data["breach_date_text"] = match.group(1)
                            break

                    # Extract what was leaked (look for information types)
                    info_patterns = [
                        r'(?:information|data).*?(?:included?|contained?|involved?).*?([^.]*(?:social security|SSN|credit card|financial|medical|personal|address|phone|email|driver|passport)[^.]*)',
                        r'(?:types?|categories?).*?(?:of\s+)?(?:information|data).*?([^.]*(?:social security|SSN|credit card|financial|medical|personal|address|phone|email|driver|passport)[^.]*)'
                    ]

                    for pattern in info_patterns:
                        match = re.search(pattern, full_text, re.IGNORECASE)
                        if match:
                            pdf_data["what_was_leaked"] = match.group(1).strip()
                            break

                    pdf_data["pdf_processed"] = True

        except Exception as e:
            logger.warning(f"pdfplumber failed for {pdf_url}: {e}")
            # Fallback to PyPDF2
            try:
                with BytesIO(response.content) as pdf_file:
                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                    text = ""
                    for page_num in range(min(3, len(pdf_reader.pages))):
                        text += pdf_reader.pages[page_num].extract_text()

                    if text.strip():
                        pdf_data["pdf_text_preview"] = text[:500]
                        pdf_data["pdf_processed"] = True

            except Exception as e2:
                pdf_data["extraction_error"] = f"Both pdfplumber and PyPDF2 failed: {e}, {e2}"
                logger.error(f"PDF extraction failed for {pdf_url}: {e2}")

    except Exception as e:
        pdf_data["extraction_error"] = str(e)
        logger.error(f"Failed to download PDF {pdf_url}: {e}")

    return pdf_data

def process_massachusetts_ag_breaches():
    """
    Enhanced Massachusetts AG Security Breach Notification processing.
    Uses annual PDF report with change detection for efficient processing.
    """
    logger.info("Starting Enhanced Massachusetts AG Security Breach Notification processing...")
    logger.info(f"Processing mode: {MA_AG_PROCESSING_MODE}")
    logger.info(f"Date filter: Only processing breaches from last {MA_AG_FILTER_DAYS_BACK} days")

    # Note: Using S3 redirect approach to bypass WAF, so no session initialization needed

    # Initialize Supabase client
    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    # Load previous state
    previous_state = load_state_file()

    # Check if we should force processing (skip change detection)
    if MA_AG_FORCE_PROCESS:
        logger.info("Force processing enabled - skipping change detection and summary page check")
        current_state = {
            "breach_count_2025": "unknown",
            "affected_count_2025": "unknown",
            "pdf_size_kb": "unknown",
            "last_checked": datetime.now().isoformat(),
            "pdf_url": MASSACHUSETTS_AG_2025_PDF_URL,
            "force_processed": True
        }
    else:
        # Get current state from summary page
        current_state = get_summary_page_info()
        if not current_state:
            logger.error("Failed to get current state from summary page")
            logger.info("Tip: Set MA_AG_FORCE_PROCESS=true to skip summary page check")
            return

        # Check if data has changed
        if not has_data_changed(current_state, previous_state):
            logger.info("No changes detected - exiting without processing PDF")
            return

    # Process the annual PDF
    logger.info("Changes detected - processing annual PDF...")
    breach_records = parse_annual_pdf_content(MASSACHUSETTS_AG_2025_PDF_URL)

    if not breach_records:
        logger.error("No breach records found in PDF")
        return

    total_processed = 0
    total_inserted = 0
    total_skipped = 0
    total_filtered_old = 0

    for breach_record in breach_records:
        total_processed += 1

        try:
            # Check if breach is recent enough (date filtering)
            date_reported_text = breach_record.get("date_reported", "")
            if not is_breach_recent(date_reported_text, MA_AG_FILTER_DAYS_BACK):
                total_filtered_old += 1
                continue

            # Create incident UID
            org_name = breach_record.get("organization_name", "")
            breach_number = breach_record.get("breach_number", "")
            incident_uid = create_incident_uid(org_name, breach_number)

            # Basic breach data
            current_time = datetime.now().isoformat()

            # Parse affected individuals
            affected_individuals = None
            ma_residents_text = breach_record.get("ma_residents_affected", "")
            if ma_residents_text and ma_residents_text.isdigit():
                affected_individuals = int(ma_residents_text)

            # Parse reported date
            reported_date = None
            if date_reported_text:
                reported_date = parse_date_flexible_ma(date_reported_text)

            # Build what was leaked from breach flags
            leaked_types = []
            if breach_record.get("ssn_breached", "").lower() == "yes":
                leaked_types.append("Social Security Numbers")
            if breach_record.get("medical_records_breached", "").lower() == "yes":
                leaked_types.append("Medical Records")
            if breach_record.get("financial_account_breached", "").lower() == "yes":
                leaked_types.append("Financial Account Information")
            if breach_record.get("drivers_licenses_breached", "").lower() == "yes":
                leaked_types.append("Driver's License Information")
            if breach_record.get("credit_debit_breached", "").lower() == "yes":
                leaked_types.append("Credit/Debit Card Numbers")

            what_was_leaked = "; ".join(leaked_types) if leaked_types else "See annual report"

            # Three-tier data structure
            ma_ag_raw = {
                "annual_pdf_url": MASSACHUSETTS_AG_2025_PDF_URL,
                "pdf_page": breach_record.get("pdf_page"),
                "pdf_table": breach_record.get("pdf_table"),
                "pdf_size_bytes": breach_record.get("pdf_size_bytes"),
                "discovery_date": current_time,
                "source_summary_page": MASSACHUSETTS_AG_SUMMARY_URL
            }

            ma_ag_derived = {
                "incident_uid": incident_uid,
                "portal_first_seen_utc": current_time,
                "annual_pdf_processed": True
            }

            ma_ag_annual_data = breach_record.copy()  # All the structured PDF data

            # Combine all raw data
            raw_data_json = {
                "massachusetts_ag_raw": ma_ag_raw,
                "massachusetts_ag_derived": ma_ag_derived,
                "massachusetts_ag_annual_data": ma_ag_annual_data
            }

            # Prepare item data for database
            item_data = {
                "source_id": SOURCE_ID_MASSACHUSETTS_AG,
                "item_url": MASSACHUSETTS_AG_2025_PDF_URL,  # Link to annual report
                "title": org_name,
                "publication_date": reported_date or current_time,
                "summary_text": f"Data breach notification for {org_name} reported to Massachusetts AG ({breach_number})",
                "affected_individuals": affected_individuals,
                "breach_date": None,  # Not available in annual report
                "reported_date": reported_date,
                "notice_document_url": MASSACHUSETTS_AG_2025_PDF_URL,
                "what_was_leaked": what_was_leaked,
                "raw_data_json": raw_data_json,
                "tags_keywords": ["massachusetts_ag", "ma_ag", "2025", "annual_report", breach_record.get("organization_type", "").lower().replace(" ", "_")]
            }

            # Insert into database
            insert_response = supabase_client.insert_item(**item_data)
            if insert_response:
                logger.info(f"Successfully inserted breach: {breach_number} - {org_name}")
                total_inserted += 1
            else:
                logger.error(f"Failed to insert breach: {breach_number} - {org_name}")
                total_skipped += 1

        except Exception as e:
            logger.error(f"Error processing breach record {breach_record.get('breach_number', 'unknown')}: {e}", exc_info=True)
            total_skipped += 1

    # Save current state
    save_state_file(current_state)

    logger.info(f"Finished Massachusetts AG processing. Total: {total_processed} processed, {total_inserted} inserted, {total_skipped} skipped, {total_filtered_old} filtered (older than {MA_AG_FILTER_DAYS_BACK} days)")

def test_massachusetts_ag_scraper():
    """
    Test function to verify the Massachusetts AG scraper works correctly.
    Tests summary page parsing and annual PDF processing without database insertion.
    """
    logger.info("Testing Massachusetts AG scraper...")

    # Note: Using S3 redirect approach to bypass WAF

    # Test S3 redirect approach directly
    logger.info("Testing S3 redirect approach for PDF download...")

    # Test direct download for the 2025 PDF
    direct_response = get_direct_download_response(MASSACHUSETTS_AG_2025_PDF_URL)
    if direct_response:
        logger.info(f"Successfully downloaded PDF directly:")
        logger.info(f"  - URL: {MASSACHUSETTS_AG_2025_PDF_URL}")
        logger.info(f"  - Size: {len(direct_response.content)} bytes")
        logger.info(f"  - Content-Type: {direct_response.headers.get('content-type', 'unknown')}")
    else:
        logger.error("Failed to download PDF directly")
        return False

    # Test state file operations
    logger.info("\n Testing state file operations...")
    test_state = {"test": "data", "timestamp": datetime.now().isoformat()}
    save_state_file(test_state)
    loaded_state = load_state_file()
    if loaded_state.get("test") == "data":
        logger.info("State file operations working")
    else:
        logger.error("State file operations failed")
        return False

    # Test change detection with mock data
    logger.info("\n Testing change detection...")
    mock_state = {
        "breach_count_2025": 922,
        "affected_count_2025": 1151829,
        "pdf_size_kb": 840.1,
        "last_checked": datetime.now().isoformat(),
        "pdf_url": MASSACHUSETTS_AG_2025_PDF_URL
    }

    has_changes = has_data_changed(mock_state, {})  # Empty previous state
    logger.info(f"Change detection (empty previous): {has_changes}")

    has_changes = has_data_changed(mock_state, mock_state)  # Same state
    logger.info(f"Change detection (same state): {has_changes}")

    # Test date filtering
    logger.info(f"\n Testing date filtering (last {MA_AG_FILTER_DAYS_BACK} days)...")

    # Test with recent date (should pass)
    recent_date = (datetime.now() - timedelta(days=2)).strftime("%d-%b-%y")
    is_recent = is_breach_recent(recent_date, MA_AG_FILTER_DAYS_BACK)
    logger.info(f"Recent date test ({recent_date}): {is_recent}")

    # Test with old date (should fail)
    old_date = (datetime.now() - timedelta(days=30)).strftime("%d-%b-%y")
    is_old = is_breach_recent(old_date, MA_AG_FILTER_DAYS_BACK)
    logger.info(f"Old date test ({old_date}): {is_old}")

    # Test annual PDF parsing (first few records only)
    if MA_AG_PROCESSING_MODE in ["ENHANCED", "FULL"]:
        logger.info(f"\n Testing annual PDF parsing...")
        try:
            # Test with a small sample to avoid timeout
            logger.info("Attempting to parse annual PDF (this may take a moment)...")
            breach_records = parse_annual_pdf_content(MASSACHUSETTS_AG_2025_PDF_URL)

            if breach_records:
                logger.info(f"Successfully parsed {len(breach_records)} breach records from annual PDF")

                # Show first 5 examples
                for i, record in enumerate(breach_records[:5]):
                    logger.info(f"  {i+1}. {record.get('breach_number')}: {record.get('organization_name')}")
                    logger.info(f"     Type: {record.get('organization_type')}")
                    logger.info(f"     MA Residents: {record.get('ma_residents_affected')}")
                    logger.info(f"     SSN: {record.get('ssn_breached')}, Medical: {record.get('medical_records_breached')}")

                if len(breach_records) > 5:
                    logger.info(f"  ... and {len(breach_records) - 5} more")
            else:
                logger.warning("No breach records found in annual PDF")

        except Exception as e:
            logger.error(f"Annual PDF parsing failed: {e}")
            return False
    else:
        logger.info("Skipping PDF parsing test (not in ENHANCED/FULL mode)")

    logger.info("Massachusetts AG scraper test completed successfully!")
    return True

if __name__ == "__main__":
    logger.info("Massachusetts AG Security Breach Scraper Started")

    # Check if this is a test run
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_massachusetts_ag_scraper()
    else:
        SUPABASE_URL = os.environ.get("SUPABASE_URL")
        SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
        else:
            logger.info("Supabase environment variables seem to be set.")
            process_massachusetts_ag_breaches()

    logger.info("Massachusetts AG Security Breach Scraper Finished")
