import os
import logging
import requests
import csv
import io
import hashlib
import time
import random
from bs4 import BeautifulSoup
from datetime import datetime, date
from urllib.parse import urljoin
from dateutil import parser as dateutil_parser # For flexible date parsing

# Assuming SupabaseClient is in utils.supabase_client
try:
    from utils.supabase_client import SupabaseClient, clean_text_for_database
    from scraper_logger import ScraperLogger
except ImportError:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from utils.supabase_client import SupabaseClient, clean_text_for_database
    from scraper_logger import ScraperLogger

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
CALIFORNIA_AG_BREACH_URL = "https://oag.ca.gov/privacy/databreach/list"
CALIFORNIA_AG_CSV_URL = "https://oag.ca.gov/privacy/databreach/list-export"
SOURCE_ID_CALIFORNIA_AG = 4 # California AG source ID

# Configuration for date filtering
# Set to None to collect all historical data (for testing)
# Set to a date string like "2025-05-27" for production filtering
# Default to beginning of current month for comprehensive coverage
# GitHub Actions should use recent date to avoid timeouts
from datetime import timedelta
default_date = "2025-06-01"
FILTER_FROM_DATE = os.environ.get("CA_AG_FILTER_FROM_DATE", default_date)

# Processing mode configuration
# BASIC: Only CSV data (fast, reliable for daily collection)
# ENHANCED: CSV + detail page URLs (moderate speed, good for regular collection)
# FULL: Everything including PDF analysis (slow, for research/analysis)
PROCESSING_MODE = os.environ.get("CA_AG_PROCESSING_MODE", "ENHANCED")  # BASIC, ENHANCED, FULL

# Rate limiting configuration
MIN_DELAY_SECONDS = 2  # Minimum delay between requests
MAX_DELAY_SECONDS = 5  # Maximum delay between requests
REQUEST_TIMEOUT = 60   # Increased timeout for detail pages
MAX_RETRIES = 3        # Maximum number of retries for failed requests

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://oag.ca.gov/' # Referer can sometimes help
}

def generate_incident_uid(organization_name: str, reported_date: str) -> str:
    """
    Generate a unique incident identifier for deduplication.
    """
    # Create a unique string combining organization and reported date
    unique_string = f"ca_ag_{organization_name}_{reported_date}".lower().replace(" ", "_")
    # Generate a hash for consistent UIDs
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

def parse_date_flexible(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO format date string or None if parsing fails.
    """
    if not date_str or date_str.strip() == "" or date_str.strip().lower() == "n/a":
        return None

    try:
        # Clean up the date string
        date_str = date_str.strip()

        # Handle multiple dates (take the first one)
        if ',' in date_str:
            date_str = date_str.split(',')[0].strip()

        # Handle common formats
        parsed_date = dateutil_parser.parse(date_str)
        return parsed_date.strftime('%Y-%m-%d')
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to parse date '{date_str}': {e}")
        return None

def parse_breach_dates(date_str: str) -> list:
    """
    Parse multiple breach dates from a comma-separated string.
    """
    if not date_str or date_str.strip() == "" or date_str.strip().lower() == "n/a":
        return []

    dates = []
    for date_part in date_str.split(','):
        date_part = date_part.strip()
        if date_part:  # Only process non-empty date parts
            parsed_date = parse_date_flexible(date_part)
            if parsed_date:
                dates.append(parsed_date)
                logger.debug(f"Successfully parsed breach date: '{date_part}' -> {parsed_date}")
            else:
                logger.warning(f"Failed to parse breach date part: '{date_part}'")

    logger.debug(f"Parsed {len(dates)} breach dates from: '{date_str}' -> {dates}")
    return dates

def rate_limit_delay():
    """
    Add a random delay between requests to avoid overwhelming the server.
    """
    delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
    logger.debug(f"Rate limiting: waiting {delay:.1f} seconds")
    time.sleep(delay)

def fetch_csv_data() -> list:
    """
    Fetch breach data from the CSV endpoint (Tier 1 - Portal Raw Data).
    """
    logger.info("Fetching California AG breach data from CSV endpoint...")

    try:
        response = requests.get(CALIFORNIA_AG_CSV_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()

        # Parse CSV data
        csv_data = []
        csv_reader = csv.DictReader(io.StringIO(response.text))

        for row in csv_reader:
            # Generate incident UID for deduplication
            incident_uid = generate_incident_uid(
                row.get('Organization Name', ''),
                row.get('Reported Date', '')
            )

            # Parse dates - handle potential column name variations
            breach_date_raw = (row.get('Date(s) of Breach (if known)', '') or
                              row.get('Date(s) of Breach  (if known)', '') or  # Extra space variant
                              '')
            breach_dates = parse_breach_dates(breach_date_raw)
            reported_date = parse_date_flexible(row.get('Reported Date', ''))

            # Debug logging for date parsing
            if breach_date_raw:
                logger.debug(f"Parsing breach dates for {row.get('Organization Name', 'Unknown')}: '{breach_date_raw}' -> {breach_dates}")

            # Create standardized breach record
            breach_record = {
                'organization_name': row.get('Organization Name', '').strip(),
                'breach_dates': breach_dates,
                'reported_date': reported_date,
                'incident_uid': incident_uid,
                'detail_url': f"https://oag.ca.gov/ecrime/databreach/reports/{incident_uid}" if incident_uid else None,
                'raw_csv_data': dict(row)
            }

            csv_data.append(breach_record)

        logger.info(f"Successfully parsed {len(csv_data)} breach records from CSV")
        return csv_data

    except Exception as e:
        logger.error(f"Failed to fetch CSV data: {e}")
        return []

def scrape_detail_page(detail_url: str) -> dict:
    """
    Scrape the detail page for additional breach information (Tier 2).
    """
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Scraping detail page (attempt {attempt + 1}/{MAX_RETRIES}): {detail_url}")

            # Add rate limiting delay before making request
            rate_limit_delay()

            response = requests.get(detail_url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            detail_data = {
                'detail_page_scraped': True,
                'detail_page_url': detail_url,
                'pdf_links': [],
                'organization_name_detail': None,
                'breach_date_detail': None
            }

            # Extract organization name from detail page
            org_name_elem = soup.find('strong', string='Organization Name:')
            if org_name_elem and org_name_elem.next_sibling:
                detail_data['organization_name_detail'] = org_name_elem.next_sibling.strip()

            # Extract breach date from detail page
            breach_date_elem = soup.find('strong', string='Date(s) of Breach (if known):')
            if breach_date_elem and breach_date_elem.next_sibling:
                detail_data['breach_date_detail'] = breach_date_elem.next_sibling.strip()

            # Find PDF links - only look for breach notification PDFs, not general site PDFs
            pdf_links = []

            # Look for PDFs in the main content area, specifically under "Sample of Notice:"
            # First, try to find the main content section
            main_content = soup.find('div', {'id': 'main-content'}) or soup

            # Look for PDF links that are likely breach notifications
            for link in main_content.find_all('a', href=True):
                href = link.get('href', '')
                if href.endswith('.pdf'):
                    # Filter out generic site PDFs (annual reports, etc.)
                    href_lower = href.lower()

                    # Skip generic annual reports and site-wide PDFs
                    skip_patterns = [
                        'data-breach-report',  # Annual reports
                        'data_breach_rpt',     # Annual reports
                        'annual',
                        'report.pdf',
                        '/agweb/pdfs/',        # General site PDFs
                        '/sites/all/files/agweb/'  # Old site structure
                    ]

                    # Check if this is a generic PDF to skip
                    should_skip = any(pattern in href_lower for pattern in skip_patterns)

                    if not should_skip:
                        # This looks like a breach notification PDF
                        full_pdf_url = urljoin(detail_url, href)
                        pdf_title = link.get_text(strip=True) or 'Sample Notification'
                        pdf_links.append({
                            'url': full_pdf_url,
                            'title': pdf_title
                        })

            detail_data['pdf_links'] = pdf_links

            logger.info(f"Found {len(detail_data['pdf_links'])} PDF links on detail page")
            return detail_data

        except Exception as e:
            last_error = e
            logger.warning(f"Attempt {attempt + 1} failed for {detail_url}: {e}")
            if attempt < MAX_RETRIES - 1:
                logger.info(f"Retrying in {MIN_DELAY_SECONDS} seconds...")
                time.sleep(MIN_DELAY_SECONDS)
            continue

    # All attempts failed
    logger.error(f"Failed to scrape detail page {detail_url} after {MAX_RETRIES} attempts: {last_error}")
    return {
        'detail_page_scraped': False,
        'detail_page_url': detail_url,
        'error': str(last_error)
    }

def extract_affected_individuals(content: str) -> dict:
    """
    Enhanced extraction of affected individuals count with confidence scoring.
    """
    import re

    result = {
        'count': None,
        'raw_text': None,
        'confidence': 'none',
        'extraction_method': None
    }

    # Enhanced patterns for affected individuals with priority order
    patterns = [
        # High confidence patterns (specific numbers with clear context)
        (r'(?:exactly|precisely)\s+(\d+(?:,\d+)*)\s+(?:individuals?|people|persons?|employees?|customers?|patients?|users?|members?)', 'high', 'exact_count'),
        (r'(\d+(?:,\d+)*)\s+(?:individuals?|people|persons?|employees?|customers?|patients?|users?|members?)\s+(?:were|are|have been)\s+(?:affected|impacted|involved|compromised)', 'high', 'direct_statement'),
        (r'(?:affects?|impacts?|involves?)\s+(\d+(?:,\d+)*)\s+(?:individuals?|people|persons?|employees?|customers?|patients?|users?|members?)', 'high', 'affects_statement'),

        # California AG specific patterns
        (r'this incident (?:affects?|impacts?) (\d+(?:,\d+)*)', 'high', 'ca_ag_incident_affects'),
        (r'breach (?:affects?|impacts?) (\d+(?:,\d+)*)', 'high', 'ca_ag_breach_affects'),
        (r'notification (?:to|for) (\d+(?:,\d+)*)', 'high', 'ca_ag_notification_count'),

        # Medium confidence patterns (approximate numbers)
        (r'(?:approximately|about|around|roughly)\s+(\d+(?:,\d+)*)\s+(?:individuals?|people|persons?|employees?|customers?|patients?|users?|members?)', 'medium', 'approximate'),
        (r'(?:up to|as many as|no more than)\s+(\d+(?:,\d+)*)\s+(?:individuals?|people|persons?|employees?|customers?|patients?|users?|members?)', 'medium', 'upper_bound'),
        (r'(?:over|more than|at least|minimum of)\s+(\d+(?:,\d+)*)\s+(?:individuals?|people|persons?|employees?|customers?|patients?|users?|members?)', 'medium', 'lower_bound'),
        (r'as many as (\d+(?:,\d+)*)', 'medium', 'as_many_as'),
        (r'potentially (\d+(?:,\d+)*)', 'medium', 'potentially_count'),

        # Lower confidence patterns (general mentions)
        (r'(\d+(?:,\d+)*)\s+(?:affected|impacted|involved|compromised)', 'low', 'general_affected'),
        (r'total of\s+(\d+(?:,\d+)*)', 'low', 'total_mention'),
        (r'(\d+(?:,\d+)*)\s+(?:records?|accounts?|files?)', 'low', 'record_count'),
        (r'(\d+(?:,\d+)*)\s+(?:california residents?)', 'medium', 'california_residents'),
        (r'(\d+(?:,\d+)*)\s+(?:current and former)', 'medium', 'current_former_count'),
    ]

    for pattern, confidence, method in patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            try:
                count = int(match.group(1).replace(',', ''))
                # Skip unrealistic numbers (too small or too large)
                if 10 <= count <= 100000000:  # Reasonable range for breach notifications (minimum 10)
                    # Additional validation: skip if the number appears in a date context
                    full_match = match.group(0)
                    if not re.search(r'\b(?:19|20)\d{2}\b', full_match):  # Not a year
                        result['count'] = count
                        result['raw_text'] = full_match
                        result['confidence'] = confidence
                        result['extraction_method'] = method
                        logger.debug(f"Found affected individuals: {count} using method {method}")
                        return result  # Return first valid match with highest confidence
            except ValueError:
                continue

    return result

def extract_data_types(content: str) -> list:
    """
    DEPRECATED: This function is being phased out in favor of storing the raw
    "What information was involved?" section text directly.

    For now, returns empty list to avoid false categorization.
    The actual breach information is stored in the what_information_involved_text field.
    """
    # Return empty list - we now store the raw section text instead of categorizing
    return []



def extract_incident_timeline(content: str) -> dict:
    """
    Extract incident timeline information from breach notification.
    """
    import re

    timeline = {}

    # Date patterns for different timeline events
    date_patterns = [
        # Discovery dates
        (r'discovered on (\w+ \d{1,2}, \d{4})', 'discovery_date'),
        (r'became aware on (\w+ \d{1,2}, \d{4})', 'discovery_date'),
        (r'learned of (?:the )?(?:incident|breach) on (\w+ \d{1,2}, \d{4})', 'discovery_date'),

        # Incident dates
        (r'incident occurred on (\w+ \d{1,2}, \d{4})', 'incident_date'),
        (r'breach took place on (\w+ \d{1,2}, \d{4})', 'incident_date'),
        (r'occurred between (\w+ \d{1,2}, \d{4}) and (\w+ \d{1,2}, \d{4})', 'incident_period'),

        # Notification dates
        (r'notifying (?:you|customers|individuals) on (\w+ \d{1,2}, \d{4})', 'notification_date'),
        (r'this letter is dated (\w+ \d{1,2}, \d{4})', 'notification_date'),

        # Containment dates
        (r'contained (?:the )?(?:incident|breach) on (\w+ \d{1,2}, \d{4})', 'containment_date'),
        (r'secured (?:the )?(?:system|data) on (\w+ \d{1,2}, \d{4})', 'containment_date'),
    ]

    for pattern, event_type in date_patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            try:
                if event_type == 'incident_period':
                    timeline['incident_start_date'] = match.group(1)
                    timeline['incident_end_date'] = match.group(2)
                else:
                    timeline[event_type] = match.group(1)
            except Exception:
                continue

    return timeline

def extract_what_information_involved(content: str) -> dict:
    """
    Extract the complete "What information was involved?" section from California AG breach notifications.
    Extracts the full text between "What information was involved?" and the next section.
    """
    import re

    result = {
        'what_information_involved_text': None,
        'extraction_method': None,
        'confidence': 'none'
    }

    # Patterns to find the "What information was involved?" section and capture until next section
    section_patterns = [
        # Standard format: "What information was involved?" until "What we are doing"
        r'what information was involved\?[\s\n]*(.+?)(?=what we are doing|what are we doing)',

        # Alternative: until "What [Company] is doing"
        r'what information was involved\?[\s\n]*(.+?)(?=what [a-zA-Z\s&,.]+ (?:is|are) doing)',

        # Alternative: until "What [we/I] did" or similar
        r'what information was involved\?[\s\n]*(.+?)(?=what (?:we|i|the company) (?:did|have done|are doing))',

        # Alternative: until next major section (starts with "What")
        r'what information was involved\?[\s\n]*(.+?)(?=\n\s*what [a-zA-Z\s]+\?)',

        # Alternative phrasings of the question
        r'what type of information was involved\?[\s\n]*(.+?)(?=what (?:we|are|the))',
        r'what personal information was involved\?[\s\n]*(.+?)(?=what (?:we|are|the))',

        # More flexible: until next section that starts with capital letter question
        r'what information was involved\?[\s\n]*(.+?)(?=\n\s*[A-Z][^a-z]*\?)',

        # Last resort: until end of paragraph or document
        r'what information was involved\?[\s\n]*(.+?)(?=\n\s*\n|\n\s*for more information|$)',
    ]

    for i, pattern in enumerate(section_patterns):
        matches = re.finditer(pattern, content, re.IGNORECASE | re.DOTALL)
        for match in matches:
            extracted_text = match.group(1).strip()

            # Clean up the extracted text but preserve structure
            extracted_text = re.sub(r'\n\s*\n', '\n\n', extracted_text)  # Normalize paragraph breaks
            extracted_text = re.sub(r'[ \t]+', ' ', extracted_text)  # Normalize spaces but keep newlines
            extracted_text = extracted_text.strip()

            # Skip if too short (likely not the real section)
            if len(extracted_text) < 30:
                continue

            # Skip if it looks like just a question or header
            if extracted_text.strip().endswith('?') and len(extracted_text) < 100:
                continue

            result['what_information_involved_text'] = extracted_text
            result['extraction_method'] = f'section_pattern_{i+1}'
            result['confidence'] = 'high' if i < 4 else 'medium'
            return result

    return result

def extract_breach_details(content: str) -> dict:
    """
    Extract additional breach details and context.
    """
    import re

    details = {}

    # Extract the "What information was involved?" section
    what_info_result = extract_what_information_involved(content)
    details['what_information_involved'] = what_info_result

    # Breach type patterns
    breach_types = {
        'cyber_attack': [r'cyber attack', r'hacking', r'malicious attack', r'unauthorized access'],
        'ransomware': [r'ransomware', r'malware', r'encryption', r'ransom'],
        'phishing': [r'phishing', r'email attack', r'fraudulent email'],
        'insider_threat': [r'employee', r'insider', r'internal'],
        'accidental': [r'accidental', r'inadvertent', r'human error', r'misconfiguration'],
        'physical': [r'theft', r'stolen', r'lost', r'physical']
    }

    detected_types = []
    for breach_type, patterns in breach_types.items():
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                detected_types.append(breach_type)
                break

    details['breach_types'] = detected_types

    # Look for remediation actions
    remediation_patterns = [
        r'credit monitoring',
        r'identity protection',
        r'fraud alert',
        r'security measures',
        r'additional safeguards',
        r'enhanced security'
    ]

    remediation_actions = []
    for pattern in remediation_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            remediation_actions.append(pattern.replace(r'\b', '').replace(r'\\', ''))

    details['remediation_offered'] = remediation_actions

    # Look for regulatory mentions
    regulatory_patterns = [
        r'hipaa', r'hitech', r'gdpr', r'ccpa', r'ferpa', r'glba',
        r'state attorney general', r'federal trade commission', r'ftc'
    ]

    regulations_mentioned = []
    for pattern in regulatory_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            regulations_mentioned.append(pattern.upper())

    details['regulations_mentioned'] = regulations_mentioned

    return details

def analyze_pdf_content(pdf_url: str) -> dict:
    """
    Enhanced PDF content analysis for comprehensive breach details (Tier 3).
    Extracts affected individuals, data types, timeline, and incident details.
    """
    try:
        logger.info(f"Analyzing PDF: {pdf_url}")

        pdf_analysis = {
            'pdf_analyzed': True,
            'pdf_url': pdf_url,
            'affected_individuals': None,
            'data_types_compromised': [],
            'incident_timeline': {},
            'breach_details': {},
            'raw_text': '',
            'extraction_confidence': 'low'  # Track confidence in extraction
        }

        # Extract PDF content using local libraries (PyPDF2 and pdfplumber)
        try:
            # Add rate limiting delay before PDF request
            rate_limit_delay()

            import requests as req_lib
            import io

            # Download PDF content
            response = req_lib.get(pdf_url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                # Try to extract text from PDF using PyPDF2 first
                try:
                    import PyPDF2
                    pdf_file = io.BytesIO(response.content)
                    pdf_reader = PyPDF2.PdfReader(pdf_file)

                    text_content = ""
                    for page in pdf_reader.pages:
                        text_content += page.extract_text() + "\n"

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
                        logger.error("Neither PyPDF2 nor pdfplumber available for PDF parsing")
                        raise Exception("No PDF parsing libraries available")

                    except Exception as pdfplumber_error:
                        logger.debug(f"pdfplumber extraction failed: {pdfplumber_error}")
                        # Last resort: try to extract any readable text from response
                        fallback_text = clean_text_for_database(response.text)
                        content = fallback_text.lower()
                        pdf_analysis['raw_text'] = fallback_text[:1000]  # Store sample
                        pdf_analysis['extraction_confidence'] = 'low'
                        logger.warning(f"Using low-confidence text extraction for {pdf_url}")
            else:
                raise Exception(f"HTTP request failed: {response.status_code}")

            # Enhanced affected individuals extraction
            pdf_analysis['affected_individuals'] = extract_affected_individuals(content)

            # Enhanced data types extraction
            pdf_analysis['data_types_compromised'] = extract_data_types(content)

            # Extract incident timeline
            pdf_analysis['incident_timeline'] = extract_incident_timeline(content)

            # Extract breach details
            pdf_analysis['breach_details'] = extract_breach_details(content)

        except Exception as e:
            logger.warning(f"Could not extract PDF content from {pdf_url}: {e}")
            pdf_analysis['extraction_confidence'] = 'failed'
            pdf_analysis['error'] = str(e)

        return pdf_analysis

    except Exception as e:
        logger.error(f"Failed to analyze PDF {pdf_url}: {e}")
        return {
            'pdf_analyzed': False,
            'pdf_url': pdf_url,
            'error': str(e),
            'extraction_confidence': 'failed'
        }

def enhance_breach_data(breach_record: dict) -> dict:
    """
    Enhance breach data by fetching detailed information (Tier 2 - Derived/Enriched).
    CRITICAL: Always returns enhanced_data even if enhancement fails.
    This ensures we never lose core breach data due to PDF/detail page failures.
    """
    # Start with core data - this is our fallback if everything fails
    enhanced_data = breach_record.copy()
    enhanced_data['enhancement_attempted'] = True
    enhanced_data['enhancement_timestamp'] = datetime.now().isoformat()
    enhanced_data['enhancement_errors'] = []  # Track any errors that occur

    try:
        # Handle different processing modes
        if PROCESSING_MODE == "BASIC":
            logger.debug(f"BASIC mode: Skipping detail scraping for {enhanced_data['organization_name']}")
            enhanced_data['tier_2_detail'] = {
                'detail_page_scraped': False,
                'skip_reason': 'BASIC mode - detail scraping disabled'
            }
            return enhanced_data

        # Construct detail page URL from organization name and CSV data
        # The URLs follow pattern: https://oag.ca.gov/ecrime/databreach/reports/sb24-XXXXXX
        # We need to find the actual URL by scraping the main page or using the CSV incident UID

        # For now, we'll try to construct the URL based on the incident UID pattern
        # This would be enhanced to actually scrape the main page for the real URLs

        # Try to find the detail page URL by scraping the main listing
        detail_url = None
        try:
            # Scrape the main page to find the actual detail URL
            # Add rate limiting delay before main page request
            rate_limit_delay()

            response = requests.get(CALIFORNIA_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find the table and look for the organization name
            org_name = enhanced_data['organization_name']

            # Look for links containing the organization name
            for link in soup.find_all('a', href=True):
                if org_name.lower() in link.get_text().lower():
                    detail_url = urljoin(CALIFORNIA_AG_BREACH_URL, link.get('href'))
                    break

        except Exception as e:
            error_msg = f"Could not find detail URL for {enhanced_data['organization_name']}: {e}"
            logger.warning(error_msg)
            enhanced_data['enhancement_errors'].append(f"Detail URL lookup failed: {str(e)}")

        # Always initialize tier_2_detail, even if we couldn't find the URL
        if detail_url:
            # Tier 2: Scrape detail page (with error handling)
            try:
                detail_data = scrape_detail_page(detail_url)
                enhanced_data['tier_2_detail'] = detail_data

                # Tier 3: Handle PDF analysis based on processing mode (with error handling)
                if PROCESSING_MODE == "FULL" and detail_data.get('pdf_links'):
                    enhanced_data['tier_3_pdf_analysis'] = []
                    for pdf_link in detail_data['pdf_links']:
                        try:
                            pdf_analysis = analyze_pdf_content(pdf_link['url'])
                            enhanced_data['tier_3_pdf_analysis'].append(pdf_analysis)
                        except Exception as pdf_error:
                            error_msg = f"PDF analysis failed for {pdf_link['url']}: {pdf_error}"
                            logger.error(error_msg)
                            enhanced_data['enhancement_errors'].append(error_msg)
                            # Still add the PDF info but mark as failed
                            enhanced_data['tier_3_pdf_analysis'].append({
                                'pdf_analyzed': False,
                                'pdf_url': pdf_link['url'],
                                'pdf_title': pdf_link.get('title', 'Unknown'),
                                'error': str(pdf_error),
                                'skip_reason': 'PDF analysis failed - error logged'
                            })

                elif detail_data.get('pdf_links'):
                    # Store PDF URLs for later analysis but don't process them now
                    logger.debug(f"ENHANCED mode: Storing PDF URLs for {enhanced_data['organization_name']} (analysis can be done separately)")
                    enhanced_data['tier_3_pdf_analysis'] = [{
                        'pdf_analyzed': False,
                        'skip_reason': f'{PROCESSING_MODE} mode - PDF analysis deferred',
                        'pdf_url': link['url'],
                        'pdf_title': link['title']
                    } for link in detail_data['pdf_links']]

            except Exception as detail_error:
                error_msg = f"Detail page scraping failed for {enhanced_data['organization_name']}: {detail_error}"
                logger.error(error_msg)
                enhanced_data['enhancement_errors'].append(error_msg)
                enhanced_data['tier_2_detail'] = {
                    'detail_page_scraped': False,
                    'detail_page_url': detail_url,
                    'error': str(detail_error),
                    'skip_reason': 'Detail page scraping failed - error logged'
                }
        else:
            # No detail URL found - still save what we have
            enhanced_data['tier_2_detail'] = {
                'detail_page_scraped': False,
                'skip_reason': 'Detail URL not found - core data preserved'
            }

        return enhanced_data

    except Exception as e:
        # CRITICAL: Even if everything fails, we still return the core breach data
        error_msg = f"Enhancement completely failed for {breach_record.get('organization_name', 'Unknown')}: {e}"
        logger.error(error_msg)
        enhanced_data['enhancement_errors'].append(f"Complete enhancement failure: {str(e)}")
        enhanced_data['tier_2_detail'] = {
            'detail_page_scraped': False,
            'skip_reason': 'Enhancement failed - core data preserved'
        }
        return enhanced_data  # Return enhanced_data with errors logged, not the original record

def process_california_ag_breaches(scraper_logger=None):
    """
    Enhanced California AG breach scraper using 3-tier approach.
    """
    logger.info("Starting enhanced California AG breach data fetch...")

    # Log processing configuration
    logger.info(f"Processing Configuration:")
    logger.info(f"  - Processing mode: {PROCESSING_MODE}")
    logger.info(f"  - Date filter: {FILTER_FROM_DATE}")
    logger.info(f"  - BASIC: CSV only | ENHANCED: CSV + URLs | FULL: Everything")

    try:
        # Initialize Supabase client
        supabase_client = SupabaseClient()

        # Tier 1: Fetch raw CSV data
        csv_breach_data = fetch_csv_data()
        if not csv_breach_data:
            logger.error("No CSV data retrieved, aborting")
            return

        # Filter breaches based on configuration
        if FILTER_FROM_DATE:
            # Production mode: filter from specified date
            try:
                filter_date = datetime.strptime(FILTER_FROM_DATE, '%Y-%m-%d').date()
                logger.info(f"Date filtering enabled: collecting breaches from {filter_date} onward")
            except ValueError:
                logger.warning(f"Invalid FILTER_FROM_DATE format '{FILTER_FROM_DATE}', using one week back")
                filter_date = (date.today() - timedelta(days=7))
        else:
            # Testing mode: collect all historical data
            filter_date = None
            logger.info("Testing mode: collecting ALL historical breach data (no date filtering)")

        filtered_breaches = []

        for breach in csv_breach_data:
            if filter_date is None:
                # No filtering - include all breaches
                filtered_breaches.append(breach)
            elif breach['reported_date']:
                try:
                    # Parse the YYYY-MM-DD format from our parse_date_flexible function
                    reported_date_obj = datetime.strptime(breach['reported_date'], '%Y-%m-%d').date()
                    if reported_date_obj >= filter_date:
                        filtered_breaches.append(breach)
                except ValueError:
                    # If date parsing fails, include the breach to be safe
                    filtered_breaches.append(breach)
            else:
                # If no reported date, include the breach
                filtered_breaches.append(breach)

        if filter_date:
            logger.info(f"Filtered to {len(filtered_breaches)} breaches (from {filter_date} onward)")
        else:
            logger.info(f"Collected {len(filtered_breaches)} total historical breaches (no filtering)")

        # Process each breach record
        processed_count = 0
        total_breaches = len(filtered_breaches)

        for i, breach_record in enumerate(filtered_breaches, 1):
            try:
                # Log progress every 10 records
                if i % 10 == 0 or i == 1:
                    logger.info(f"Processing breach {i}/{total_breaches} ({(i/total_breaches)*100:.1f}%)")
                    if scraper_logger:
                        scraper_logger.log_progress(
                            f"Processing breach {i}/{total_breaches}",
                            items_processed=i,
                            current_page=i,
                            total_pages=total_breaches
                        )

                # Tier 2: Enhance with additional data
                enhanced_record = enhance_breach_data(breach_record)

                # Extract enhanced data for database fields
                affected_individuals = None
                data_types_compromised = []
                notice_document_url = None

                # Extract from enhanced PDF analysis if available
                what_information_involved_text = None
                if enhanced_record.get('tier_3_pdf_analysis'):
                    for pdf_analysis in enhanced_record['tier_3_pdf_analysis']:
                        # Extract affected individuals with confidence scoring
                        if pdf_analysis.get('affected_individuals'):
                            if isinstance(pdf_analysis['affected_individuals'], dict):
                                # New enhanced format with confidence
                                affected_individuals = pdf_analysis['affected_individuals'].get('count')
                            else:
                                # Legacy format (simple number)
                                affected_individuals = pdf_analysis['affected_individuals']

                        # Extract data types
                        if pdf_analysis.get('data_types_compromised'):
                            data_types_compromised.extend(pdf_analysis['data_types_compromised'])

                        # Extract "What information was involved?" text
                        breach_details = pdf_analysis.get('breach_details', {})
                        if breach_details and isinstance(breach_details, dict):
                            what_info = breach_details.get('what_information_involved', {})
                            if what_info and isinstance(what_info, dict):
                                what_information_involved_text = what_info.get('what_information_involved_text')
                                if what_information_involved_text:
                                    break  # Use the first successful extraction

                # Get PDF URL for notice_document_url
                if enhanced_record.get('tier_2_detail', {}).get('pdf_links'):
                    notice_document_url = enhanced_record['tier_2_detail']['pdf_links'][0]['url']

                # Create enhanced summary
                summary_parts = [f"Data breach reported by {enhanced_record['organization_name']}"]
                if data_types_compromised:
                    summary_parts.append(f"Data types involved: {', '.join(data_types_compromised)}")
                if affected_individuals:
                    summary_parts.append(f"Affected individuals: {affected_individuals:,}")

                summary_text = ". ".join(summary_parts)

                # Create enhanced full content
                content_parts = [
                    f"Organization: {enhanced_record['organization_name']}",
                    f"Breach Date(s): {', '.join(enhanced_record['breach_dates']) if enhanced_record['breach_dates'] else 'Not specified'}",
                    f"Reported Date: {enhanced_record['reported_date'] or 'Not specified'}"
                ]

                if data_types_compromised:
                    content_parts.append(f"Data Types Compromised: {', '.join(data_types_compromised)}")
                if affected_individuals:
                    content_parts.append(f"Affected Individuals: {affected_individuals:,}")
                if notice_document_url:
                    content_parts.append(f"Notification Document: {notice_document_url}")
                if what_information_involved_text:
                    content_parts.append(f"What Information Was Involved: {what_information_involved_text}")

                full_content = "\n".join(content_parts)

                # Convert to database format - be conservative with field mapping
                # Enhanced breach date handling - capture original data regardless of parsing success
                breach_date_for_db = None
                original_breach_date_text = enhanced_record['raw_csv_data'].get('Date(s) of Breach  (if known)', '') or enhanced_record['raw_csv_data'].get('Date(s) of Breach (if known)', '')

                # Always log what we're working with
                if original_breach_date_text:
                    logger.debug(f"Processing breach dates for {enhanced_record['organization_name']}: '{original_breach_date_text}' -> parsed: {enhanced_record['breach_dates']}")

                # Use all dates for database field (now TEXT type), store all dates in JSON
                if enhanced_record['breach_dates'] and len(enhanced_record['breach_dates']) > 0:
                    try:
                        # The parse_breach_dates function already returns YYYY-MM-DD format
                        # Store all dates in database field (now TEXT type supports multiple dates)
                        if len(enhanced_record['breach_dates']) == 1:
                            breach_date_for_db = enhanced_record['breach_dates'][0]
                            logger.debug(f"Using single parsed breach date for database: {breach_date_for_db}")
                        else:
                            # Multiple dates - join with commas for TEXT field
                            breach_date_for_db = ", ".join(enhanced_record['breach_dates'])
                            logger.debug(f"Using multiple parsed breach dates for database: {breach_date_for_db}")
                    except (IndexError, TypeError) as e:
                        logger.warning(f"Failed to use parsed breach date for {enhanced_record['organization_name']}: {e}")
                        breach_date_for_db = None

                # If we have original text but no parsed dates, log this for investigation
                if original_breach_date_text and not enhanced_record['breach_dates']:
                    logger.info(f"Breach date text present but not parsed for {enhanced_record['organization_name']}:'{original_breach_date_text}'")
                elif original_breach_date_text and enhanced_record['breach_dates']:
                    logger.debug(f"Successfully parsed breach dates:'{original_breach_date_text}'-> {enhanced_record['breach_dates']}")

                # Determine what_was_leaked value with PDF URL fallback
                what_was_leaked_value = what_information_involved_text
                if not what_was_leaked_value and notice_document_url:
                    what_was_leaked_value = f"See breach details in PDF: {notice_document_url}"
                    logger.info(f"Using PDF URL fallback for what_was_leaked: {enhanced_record['organization_name']}")

                db_item = {
                    'source_id': SOURCE_ID_CALIFORNIA_AG,
                    'item_url': enhanced_record.get('tier_2_detail', {}).get('detail_page_url', CALIFORNIA_AG_BREACH_URL),
                    'title': enhanced_record['organization_name'],
                    'publication_date': enhanced_record['reported_date'],
                    'summary_text': summary_text,
                    'full_content': full_content,
                    'reported_date': enhanced_record['reported_date'],
                    'breach_date': breach_date_for_db,
                    'affected_individuals': affected_individuals,
                    'notice_document_url': notice_document_url,
                    'what_was_leaked': what_was_leaked_value,  # New dedicated column for extracted section (with PDF URL fallback)
                    'raw_data_json': {
                        'scraper_version': '4.2_enhanced_breach_dates',
                        'tier_1_csv_data': enhanced_record['raw_csv_data'],
                        'tier_2_enhanced': {
                            'incident_uid': enhanced_record['incident_uid'],
                            'breach_dates_all': enhanced_record['breach_dates'],
                            'breach_dates_original_text': original_breach_date_text,  # Always preserve original
                            'breach_dates_parsing_success': len(enhanced_record['breach_dates']) > 0,
                            'enhancement_attempted': enhanced_record.get('enhancement_attempted', False),
                            'enhancement_timestamp': enhanced_record.get('enhancement_timestamp'),
                            'detail_page_data': enhanced_record.get('tier_2_detail', {})
                        },
                        'tier_3_pdf_analysis': enhanced_record.get('tier_3_pdf_analysis', []),
                        # Store data types in raw_data_json for now (until schema is updated)
                        'data_types_compromised': data_types_compromised,
                        'what_information_involved_text': what_information_involved_text,  # Store for easy access
                        'pdf_analysis_summary': {
                            'affected_individuals_extracted': affected_individuals,
                            'data_types_found': data_types_compromised,
                            'what_information_involved_extracted': bool(what_information_involved_text),
                            'pdf_documents_analyzed': len(enhanced_record.get('tier_3_pdf_analysis', []))
                        }
                    }
                }

                # Note: data_types_compromised field is stored in raw_data_json
                # The database schema may not have this field in all instances

                # Log enhancement errors if any occurred (but still proceed with database insertion)
                if enhanced_record.get('enhancement_errors'):
                    logger.warning(f"Enhancement errors for {enhanced_record['organization_name']}: {enhanced_record['enhancement_errors']}")
                    # Still proceed - we have the core breach data which is most important

                # Smart duplicate handling: Check if item exists and if it needs enhancement updates
                item_url = db_item['item_url']
                enhancement_status = supabase_client.get_item_enhancement_status(item_url)

                if enhancement_status['exists']:
                    # Item exists - check if we should update it with better enhancement data
                    should_update = False
                    update_reasons = []

                    # Check if previous enhancement had errors and we now have successful data
                    if enhancement_status['has_enhancement_errors'] and not enhanced_record.get('enhancement_errors'):
                        should_update = True
                        update_reasons.append("previous enhancement had errors, now successful")

                    # Check if we now have PDF analysis when we didn't before
                    if not enhancement_status['has_pdf_analysis'] and enhanced_record.get('tier_3_pdf_analysis'):
                        has_successful_pdf = any(
                            pdf.get('pdf_analyzed', False)
                            for pdf in enhanced_record['tier_3_pdf_analysis']
                            if isinstance(pdf, dict)
                        )
                        if has_successful_pdf:
                            should_update = True
                            update_reasons.append("now has successful PDF analysis")

                    # Check if we now have affected individuals count when we didn't before
                    current_affected = enhancement_status.get('affected_individuals')
                    new_affected = db_item.get('affected_individuals')
                    if not current_affected and new_affected:
                        should_update = True
                        update_reasons.append("now has affected individuals count")

                    # Check if we now have notice document URL when we didn't before
                    current_notice_url = enhancement_status.get('notice_document_url')
                    new_notice_url = db_item.get('notice_document_url')
                    if not current_notice_url and new_notice_url:
                        should_update = True
                        update_reasons.append("now has notice document URL")

                    # Check if we now have "What information was involved?" text when we didn't before
                    current_raw_data = enhancement_status.get('raw_data_json', {})
                    current_what_info = current_raw_data.get('what_information_involved_text') if isinstance(current_raw_data, dict) else None
                    new_what_info = what_information_involved_text
                    if not current_what_info and new_what_info:
                        should_update = True
                        update_reasons.append("now has 'What information was involved?' text")

                    if should_update:
                        logger.info(f"Updating existing item with enhanced data: {enhanced_record['organization_name']}")
                        logger.info(f"   Update reasons: {', '.join(update_reasons)}")

                        # Update the existing item with enhanced data
                        update_success = supabase_client.update_item_enhancement(
                            enhancement_status['item_id'],
                            db_item
                        )

                        if update_success:
                            processed_count += 1
                            logger.info(f"Successfully updated existing item: {enhanced_record['organization_name']}")
                        else:
                            logger.error(f"Failed to update existing item: {enhanced_record['organization_name']}")
                    else:
                        logger.info(f"Skipping existing item (no enhancement improvements): {enhanced_record['organization_name']}")

                    continue

                # CRITICAL: Always attempt database insertion - core breach data must be saved
                try:
                    insert_result = supabase_client.insert_item(**db_item)
                    if insert_result:
                        processed_count += 1
                        enhancement_status = "with enhancement errors" if enhanced_record.get('enhancement_errors') else "successfully"
                        logger.info(f"Saved breach data {enhancement_status}: {enhanced_record['organization_name']}")
                    else:
                        logger.error(f"Database insertion failed: {enhanced_record['organization_name']}")
                except Exception as db_error:
                    logger.error(f"Database insertion error for {enhanced_record['organization_name']}: {db_error}")
                    # Continue processing other records even if this one fails

            except Exception as e:
                # CRITICAL: Even if record processing completely fails, log it and continue
                # We must not let one bad record stop the entire scraper
                org_name = breach_record.get('organization_name', 'Unknown')
                logger.error(f"Complete failure processing breach record for {org_name}: {e}")
                logger.error(f"   This breach will be missed in this run but scraper continues")
                # Continue to next record - don't let one failure stop everything

        logger.info(f"California AG enhanced breach fetch completed. Processed {processed_count} items.")

        # Return statistics for logging
        return {
            'processed_count': processed_count,
            'inserted_count': processed_count,  # For CA AG, processed = inserted
            'skipped_count': total_breaches - processed_count,
            'total_breaches': total_breaches
        }

    except Exception as e:
        logger.error(f"Unexpected error in California AG breach fetch: {e}")
        raise  # Re-raise to be caught by main error handling

# Legacy function name for compatibility
def fetch_california_ag_breaches(scraper_logger=None):
    """
    Legacy function name - calls the enhanced process function.
    """
    return process_california_ag_breaches(scraper_logger)

if __name__ == "__main__":
    # Initialize scraper logger
    scraper_logger = ScraperLogger("california_ag", SOURCE_ID_CALIFORNIA_AG)
    run_id = scraper_logger.start_run()

    logger.info("California AG Security Breach Scraper Started")

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    success = False
    error_message = None
    items_processed = 0
    items_inserted = 0
    items_skipped = 0

    try:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            error_message = "CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set."
            logger.error(error_message)
            scraper_logger.log_error(error_message, "configuration")
        else:
            logger.info("Supabase environment variables seem to be set.")
            scraper_logger.log_progress("Starting California AG breach processing")

            # Run the main processing function
            result = process_california_ag_breaches(scraper_logger)

            # Extract statistics from result if available
            if isinstance(result, dict):
                items_processed = result.get('processed_count', 0)
                items_inserted = result.get('inserted_count', 0)
                items_skipped = result.get('skipped_count', 0)

            success = True
            logger.info("California AG Security Breach Scraper Finished Successfully")

    except Exception as e:
        error_message = f"Scraper failed with error: {str(e)}"
        logger.error(error_message, exc_info=True)
        scraper_logger.log_error(error_message, "execution")

    finally:
        # End the scraper run with final statistics
        scraper_logger.end_run(
            success=success,
            items_processed=items_processed,
            items_inserted=items_inserted,
            items_skipped=items_skipped,
            error_message=error_message
        )
