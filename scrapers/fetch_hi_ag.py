import os
import logging
import requests
import hashlib
import time
import random
import re
import io
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from urllib.parse import urljoin
from dateutil import parser as dateutil_parser

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
HAWAII_AG_BREACH_URL = "https://cca.hawaii.gov/ocp/notices/security-breach/"
SOURCE_ID_HAWAII_AG = 6

# Configuration for date filtering
# Set to None to collect all historical data (for testing)
# Set to a date string like "2025-01-27" for production filtering
# Default to beginning of current month for comprehensive coverage
default_date = "2025-06-01"
FILTER_FROM_DATE = os.environ.get("HI_AG_FILTER_FROM_DATE", default_date)

# Processing mode configuration
# BASIC: Only table data (fast, reliable for daily collection)
# ENHANCED: Table + PDF URLs (moderate speed, good for regular collection)
# FULL: Everything including PDF analysis (slow, for research/analysis)
PROCESSING_MODE = os.environ.get("HI_AG_PROCESSING_MODE", "ENHANCED")  # BASIC, ENHANCED, FULL

# Rate limiting configuration
MIN_DELAY_SECONDS = 2  # Minimum delay between requests
MAX_DELAY_SECONDS = 5  # Maximum delay between requests
REQUEST_TIMEOUT = 60   # Increased timeout for PDF downloads
MAX_RETRIES = 3        # Maximum number of retries for failed requests

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://cca.hawaii.gov/'
}

def generate_incident_uid(case_number: str, organization_name: str) -> str:
    """
    Generate a unique incident identifier for deduplication using case number.
    """
    # Create a unique string combining case number and organization
    unique_string = f"hi_ag_{case_number}_{organization_name}".lower().replace(" ", "_")
    # Generate a hash for consistent UIDs
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

def parse_date_flexible(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO format date string or None if parsing fails.
    """
    if not date_str or date_str.strip() == "" or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided']:
        return None

    try:
        # Clean up the date string
        date_str = date_str.strip()

        # Skip if it looks like a company name (contains common business words)
        business_indicators = ['inc', 'llc', 'corp', 'company', 'ltd', 'dental', 'medical', 'health', 'services', 'group', 'associates']
        if any(indicator in date_str.lower() for indicator in business_indicators):
            logger.warning(f"Skipping date parsing for '{date_str}' - appears to be a company name")
            return None

        # Handle specific Hawaii AG date formats like "2024/03.18"
        if '/' in date_str and '.' in date_str:
            try:
                # Convert "2024/03.18" to "2024/03/18"
                date_str = date_str.replace('.', '/')
            except:
                pass

        # Handle multiple dates (take the first one)
        if ',' in date_str:
            date_str = date_str.split(',')[0].strip()

        # Parse the date
        parsed_date = dateutil_parser.parse(date_str)
        return parsed_date.strftime('%Y-%m-%d')
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def parse_affected_individuals(residents_str: str) -> int | None:
    """
    Parse the number of affected Hawaii residents from the table column.
    """
    if not residents_str or residents_str.strip() == "":
        return None

    try:
        # Remove commas and extract numbers
        clean_str = residents_str.replace(',', '').strip()

        # Extract first number found
        import re
        numbers = re.findall(r'\d+', clean_str)
        if numbers:
            count = int(numbers[0])
            # Sanity check - reasonable range for breach notifications
            if 10 <= count <= 100000000:
                return count
            else:
                logger.warning(f"Affected individuals count {count} outside reasonable range")
                return None
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not parse affected individuals from '{residents_str}': {e}")

    return None

def normalize_breach_type(breach_type_str: str) -> list:
    """
    Normalize breach type string into standardized categories.
    """
    if not breach_type_str:
        return []

    breach_type_lower = breach_type_str.lower()
    categories = []

    # Map Hawaii AG breach types to standardized categories
    type_mapping = {
        'hackers/unauthorized access': ['cyber_attack', 'unauthorized_access'],
        'stolen laptops, computers & equipment': ['physical_theft', 'device_theft'],
        'release/display of information': ['accidental_disclosure', 'data_exposure'],
        'data theft by employee or contractor': ['insider_threat', 'employee_theft'],
        'lost in transit': ['physical_loss', 'transit_loss'],
        'phishing': ['phishing', 'email_attack']
    }

    for hawaii_type, standard_types in type_mapping.items():
        if hawaii_type in breach_type_lower:
            categories.extend(standard_types)
            break

    # If no specific mapping found, use the original as a category
    if not categories:
        categories.append(breach_type_str.lower().replace(' ', '_').replace('/', '_'))

    return categories

def rate_limit_delay():
    """
    Add a random delay between requests to avoid overwhelming the server.
    """
    delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
    logger.debug(f"Rate limiting: waiting {delay:.1f} seconds")
    time.sleep(delay)

def extract_what_information_involved(content: str) -> dict:
    """
    Extract information about what data was compromised from Hawaii AG breach notifications.
    Adapted from California AG pattern for Hawaii-specific content.
    """
    result = {
        'what_information_involved_text': None,
        'extraction_method': None,
        'confidence': 'none'
    }

    # Patterns to find data compromise information in Hawaii breach notifications
    section_patterns = [
        # Standard format: "What information was involved?" until next section
        r'what information was involved\?[\s\n]*(.+?)(?=what we are doing|what are we doing)',

        # Alternative: "What personal information was affected?"
        r'what personal information was affected\?[\s\n]*(.+?)(?=what (?:we|are|the))',

        # Alternative: "What data was compromised?"
        r'what data was compromised\?[\s\n]*(.+?)(?=what (?:we|are|the))',

        # Alternative: "Information involved" section
        r'information involved[\s\n]*(.+?)(?=\n\s*what [a-zA-Z\s]+\?)',

        # Look for "The following information" patterns
        r'the following information[^.]*:[\s\n]*(.+?)(?=\n\s*\n|\n\s*for more information|$)',

        # Look for "may have included" patterns
        r'may have included[\s\n]*(.+?)(?=\n\s*\n|\n\s*for more information|$)',

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
            result['extraction_method'] = f'hawaii_pattern_{i+1}'
            result['confidence'] = 'high' if i < 4 else 'medium'
            return result

    return result

def extract_affected_individuals_from_pdf(content: str) -> dict:
    """
    Enhanced extraction of affected individuals count from PDF content.
    """
    result = {
        'count': None,
        'raw_text': None,
        'confidence': 'none',
        'extraction_method': None
    }

    # Enhanced patterns for affected individuals with priority order
    patterns = [
        # High confidence patterns (specific numbers with clear context)
        (r'(?:exactly|precisely)\s+(\d+(?:,\d+)*)\s+(?:individuals?|people|persons?|hawaii residents?)', 'high', 'exact_count'),
        (r'(\d+(?:,\d+)*)\s+(?:hawaii residents?|individuals?|people|persons?)\s+(?:were|are|have been)\s+(?:affected|impacted|involved|compromised)', 'high', 'direct_statement'),
        (r'(?:affects?|impacts?|involves?)\s+(\d+(?:,\d+)*)\s+(?:hawaii residents?|individuals?|people|persons?)', 'high', 'affects_statement'),

        # Hawaii AG specific patterns
        (r'this incident (?:affects?|impacts?) (\d+(?:,\d+)*)', 'high', 'hi_ag_incident_affects'),
        (r'breach (?:affects?|impacts?) (\d+(?:,\d+)*)', 'high', 'hi_ag_breach_affects'),
        (r'notification (?:to|for) (\d+(?:,\d+)*)', 'high', 'hi_ag_notification_count'),

        # Medium confidence patterns (approximate numbers)
        (r'(?:approximately|about|around|roughly)\s+(\d+(?:,\d+)*)\s+(?:hawaii residents?|individuals?|people|persons?)', 'medium', 'approximate'),
        (r'(?:up to|as many as|no more than)\s+(\d+(?:,\d+)*)\s+(?:hawaii residents?|individuals?|people|persons?)', 'medium', 'upper_bound'),
        (r'(?:over|more than|at least|minimum of)\s+(\d+(?:,\d+)*)\s+(?:hawaii residents?|individuals?|people|persons?)', 'medium', 'lower_bound'),

        # Lower confidence patterns (general mentions)
        (r'(\d+(?:,\d+)*)\s+(?:affected|impacted|involved|compromised)', 'low', 'general_affected'),
        (r'total of\s+(\d+(?:,\d+)*)', 'low', 'total_mention'),
        (r'(\d+(?:,\d+)*)\s+(?:hawaii residents?)', 'medium', 'hawaii_residents'),
    ]

    for pattern, confidence, method in patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            try:
                count = int(match.group(1).replace(',', ''))
                # Skip unrealistic numbers (too small or too large)
                if 10 <= count <= 100000000:  # Reasonable range for breach notifications
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

def analyze_pdf_content(pdf_url: str) -> dict:
    """
    Enhanced PDF content analysis for comprehensive breach details (Tier 3).
    Extracts affected individuals, data types, and incident details from Hawaii AG PDFs.
    """
    try:
        logger.info(f"Analyzing Hawaii AG PDF: {pdf_url}")

        pdf_analysis = {
            'pdf_analyzed': True,
            'pdf_url': pdf_url,
            'affected_individuals': None,
            'what_information_involved': {},
            'raw_text': '',
            'extraction_confidence': 'low'  # Track confidence in extraction
        }

        # Extract PDF content using local libraries (PyPDF2 and pdfplumber)
        try:
            # Add rate limiting delay before PDF request
            rate_limit_delay()

            # Download PDF content
            response = requests.get(pdf_url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
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
            pdf_analysis['affected_individuals'] = extract_affected_individuals_from_pdf(content)

            # Extract "What information was involved?" section
            pdf_analysis['what_information_involved'] = extract_what_information_involved(content)

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

def fetch_table_data() -> list:
    """
    Fetch breach data from the Hawaii AG table (Tier 1 - Portal Raw Data).
    """
    logger.info("Fetching Hawaii AG breach data from table...")

    try:
        response = requests.get(HAWAII_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Hawaii AG breach data page: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')

    # Hawaii AG site structure:
    # Data is typically within a <table>. The table might be inside a div with class 'entry-content'.
    # Each row <tr> in <tbody> is a breach notification.

    data_table = None
    entry_content_div = soup.find('div', class_='entry-content')  # Common WordPress class
    if entry_content_div:
        data_table = entry_content_div.find('table')

    if not data_table:
        # Fallback: try to find any table if not in 'entry-content'
        all_tables = soup.find_all('table')
        if all_tables:
            logger.info(f"Found {len(all_tables)} table(s) outside 'entry-content'. Trying the first one.")
            data_table = all_tables[0]  # This might be fragile
        else:
            logger.error("Could not find the breach data table (neither in 'entry-content' nor any other table on page). Page structure might have changed.")
            return []

    tbody = data_table.find('tbody')
    if not tbody:
        logger.error("Table found, but it does not contain a <tbody> element. Cannot process rows.")
        return []

    notifications = tbody.find_all('tr')
    logger.info(f"Found {len(notifications)} potential breach notifications in the table.")

    if not notifications:
        logger.warning("No rows found in the table body. The table might be empty or structured differently.")
        return []

    table_data = []

    # Column headers from Firecrawl analysis: Date Notified, Case Number, Breached Entity Name, Breach type, Hawaii Residents Impacted, Link to Letter
    for row_idx, row in enumerate(notifications):
        cols = row.find_all('td')

        if len(cols) < 5:  # Expecting at least 5 columns based on Firecrawl analysis
            logger.warning(f"Skipping row {row_idx+1} due to insufficient columns ({len(cols)}). Row content: {[c.get_text(strip=True)[:30] for c in cols]}")
            continue

        try:
            # Extract all available columns
            date_notified_str = cols[0].get_text(strip=True)
            case_number = cols[1].get_text(strip=True)
            breached_entity_name = cols[2].get_text(strip=True)
            breach_type = cols[3].get_text(strip=True)
            hawaii_residents_impacted = cols[4].get_text(strip=True)

            # Extract PDF link if available
            pdf_link = None
            if len(cols) > 5:  # Link to Letter column
                pdf_link_tag = cols[5].find('a', href=True)
                if pdf_link_tag:
                    pdf_link = urljoin(HAWAII_AG_BREACH_URL, pdf_link_tag['href'])

            if not breached_entity_name or not date_notified_str:
                logger.warning(f"Skipping row {row_idx+1} due to missing essential data: Entity='{breached_entity_name}', Date='{date_notified_str}'")
                continue

            # Generate incident UID for deduplication
            incident_uid = generate_incident_uid(case_number, breached_entity_name)

            # Parse dates
            reported_date = parse_date_flexible(date_notified_str)

            # Parse affected individuals
            affected_individuals = parse_affected_individuals(hawaii_residents_impacted)

            # Normalize breach type
            breach_categories = normalize_breach_type(breach_type)

            # Create standardized breach record
            breach_record = {
                'case_number': case_number,
                'organization_name': breached_entity_name,
                'reported_date': reported_date,
                'breach_type_original': breach_type,
                'breach_categories': breach_categories,
                'affected_individuals': affected_individuals,
                'pdf_url': pdf_link,
                'incident_uid': incident_uid,
                'raw_table_data': {
                    'date_notified_original': date_notified_str,
                    'case_number': case_number,
                    'breached_entity_name': breached_entity_name,
                    'breach_type': breach_type,
                    'hawaii_residents_impacted': hawaii_residents_impacted,
                    'pdf_link': pdf_link
                }
            }

            table_data.append(breach_record)

        except Exception as e:
            logger.error(f"Error processing row {row_idx+1}: {e}")
            continue

    logger.info(f"Successfully parsed {len(table_data)} breach records from table")
    return table_data

def enhance_breach_data(breach_record: dict) -> dict:
    """
    Enhance breach data with PDF analysis (Tier 2 - Derived/Enriched).
    CRITICAL: Always returns enhanced_data even if enhancement fails.
    This ensures we never lose core breach data due to PDF failures.
    """
    # Start with core data - this is our fallback if everything fails
    enhanced_data = breach_record.copy()
    enhanced_data['enhancement_attempted'] = True
    enhanced_data['enhancement_timestamp'] = datetime.now().isoformat()
    enhanced_data['enhancement_errors'] = []  # Track any errors that occur

    try:
        # Handle different processing modes
        if PROCESSING_MODE == "BASIC":
            logger.debug(f"BASIC mode: Skipping PDF analysis for {enhanced_data['organization_name']}")
            enhanced_data['tier_2_pdf_analysis'] = {
                'pdf_analyzed': False,
                'skip_reason': 'BASIC mode - PDF analysis disabled'
            }
            return enhanced_data

        # Tier 2: PDF Analysis (if PDF URL available)
        if enhanced_data.get('pdf_url') and PROCESSING_MODE in ["ENHANCED", "FULL"]:
            try:
                if PROCESSING_MODE == "FULL":
                    # Full PDF analysis
                    pdf_analysis = analyze_pdf_content(enhanced_data['pdf_url'])
                    enhanced_data['tier_2_pdf_analysis'] = pdf_analysis
                else:
                    # ENHANCED mode: Store PDF URL for later analysis but don't process now
                    enhanced_data['tier_2_pdf_analysis'] = {
                        'pdf_analyzed': False,
                        'skip_reason': f'{PROCESSING_MODE} mode - PDF analysis deferred',
                        'pdf_url': enhanced_data['pdf_url']
                    }

            except Exception as pdf_error:
                error_msg = f"PDF analysis failed for {enhanced_data['organization_name']}: {pdf_error}"
                logger.error(error_msg)
                enhanced_data['enhancement_errors'].append(error_msg)
                enhanced_data['tier_2_pdf_analysis'] = {
                    'pdf_analyzed': False,
                    'pdf_url': enhanced_data.get('pdf_url'),
                    'error': str(pdf_error),
                    'skip_reason': 'PDF analysis failed - error logged'
                }
        else:
            # No PDF URL available
            enhanced_data['tier_2_pdf_analysis'] = {
                'pdf_analyzed': False,
                'skip_reason': 'No PDF URL available'
            }

        return enhanced_data

    except Exception as e:
        # CRITICAL: Even if everything fails, we still return the core breach data
        error_msg = f"Enhancement completely failed for {breach_record.get('organization_name', 'Unknown')}: {e}"
        logger.error(error_msg)
        enhanced_data['enhancement_errors'].append(f"Complete enhancement failure: {str(e)}")
        enhanced_data['tier_2_pdf_analysis'] = {
            'pdf_analyzed': False,
            'skip_reason': 'Enhancement failed - core data preserved'
        }
        return enhanced_data  # Return enhanced_data with errors logged, not the original record

def process_hawaii_ag_breaches():
    """
    Enhanced Hawaii AG breach scraper using 3-tier approach.
    """
    logger.info("Starting enhanced Hawaii AG breach data fetch...")

    # Log processing configuration
    logger.info(f"Processing Configuration:")
    logger.info(f"  - Processing mode: {PROCESSING_MODE}")
    logger.info(f"  - Date filter: {FILTER_FROM_DATE}")
    logger.info(f"  - BASIC: Table only | ENHANCED: Table + PDF URLs | FULL: Everything")

    try:
        # Initialize Supabase client
        supabase_client = SupabaseClient()

        # Tier 1: Fetch raw table data
        table_breach_data = fetch_table_data()
        if not table_breach_data:
            logger.error("No table data retrieved, aborting")
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

        for breach in table_breach_data:
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

                # Tier 2: Enhance with PDF analysis
                enhanced_record = enhance_breach_data(breach_record)

                # Extract enhanced data for database fields
                affected_individuals = enhanced_record.get('affected_individuals')
                notice_document_url = enhanced_record.get('pdf_url')

                # Extract from enhanced PDF analysis if available
                what_information_involved_text = None
                if enhanced_record.get('tier_2_pdf_analysis', {}).get('pdf_analyzed'):
                    pdf_analysis = enhanced_record['tier_2_pdf_analysis']

                    # Extract affected individuals with confidence scoring (PDF might have more accurate count)
                    if pdf_analysis.get('affected_individuals'):
                        if isinstance(pdf_analysis['affected_individuals'], dict):
                            # New enhanced format with confidence
                            pdf_affected = pdf_analysis['affected_individuals'].get('count')
                            if pdf_affected:
                                affected_individuals = pdf_affected  # Use PDF count if available
                        else:
                            # Legacy format (simple number)
                            affected_individuals = pdf_analysis['affected_individuals']

                    # Extract "What information was involved?" text
                    what_info = pdf_analysis.get('what_information_involved', {})
                    if what_info and isinstance(what_info, dict):
                        what_information_involved_text = what_info.get('what_information_involved_text')

                # Create enhanced summary
                summary_parts = [f"Data breach reported by {enhanced_record['organization_name']}"]
                if enhanced_record.get('breach_categories'):
                    summary_parts.append(f"Breach type: {', '.join(enhanced_record['breach_categories'])}")
                if affected_individuals:
                    summary_parts.append(f"Affected Hawaii residents: {affected_individuals:,}")

                summary_text = ". ".join(summary_parts)

                # Create enhanced full content
                content_parts = [
                    f"Organization: {enhanced_record['organization_name']}",
                    f"Case Number: {enhanced_record['case_number']}",
                    f"Reported Date: {enhanced_record['reported_date'] or 'Not specified'}",
                    f"Breach Type: {enhanced_record['breach_type_original']}"
                ]

                if enhanced_record.get('breach_categories'):
                    content_parts.append(f"Breach Categories: {', '.join(enhanced_record['breach_categories'])}")
                if affected_individuals:
                    content_parts.append(f"Hawaii Residents Affected: {affected_individuals:,}")
                if notice_document_url:
                    content_parts.append(f"Notification Document: {notice_document_url}")
                if what_information_involved_text:
                    content_parts.append(f"What Information Was Involved: {what_information_involved_text}")

                full_content = "\n".join(content_parts)

                # Determine what_was_leaked value with PDF URL fallback
                what_was_leaked_value = what_information_involved_text
                if not what_was_leaked_value and notice_document_url:
                    what_was_leaked_value = f"See breach details in PDF: {notice_document_url}"
                    logger.info(f"Using PDF URL fallback for what_was_leaked: {enhanced_record['organization_name']}")

                # Create tags including breach categories
                tags = ["hawaii_ag", "hi_breach", "security_notification"]
                if enhanced_record.get('breach_categories'):
                    tags.extend(enhanced_record['breach_categories'])

                db_item = {
                    'source_id': SOURCE_ID_HAWAII_AG,
                    'item_url': notice_document_url or f"{HAWAII_AG_BREACH_URL}#{enhanced_record['case_number']}",
                    'title': enhanced_record['organization_name'],
                    'publication_date': enhanced_record['reported_date'],
                    'summary_text': summary_text,
                    'full_content': full_content,
                    'reported_date': enhanced_record['reported_date'],
                    'affected_individuals': affected_individuals,
                    'notice_document_url': notice_document_url,
                    'what_was_leaked': what_was_leaked_value,  # New dedicated column for extracted section (with PDF URL fallback)
                    'tags_keywords': list(set(tags)),
                    'raw_data_json': {
                        'scraper_version': '2.0_enhanced_hawaii_ag',
                        'tier_1_table_data': enhanced_record['raw_table_data'],
                        'tier_2_enhanced': {
                            'incident_uid': enhanced_record['incident_uid'],
                            'case_number': enhanced_record['case_number'],
                            'breach_type_original': enhanced_record['breach_type_original'],
                            'breach_categories': enhanced_record['breach_categories'],
                            'enhancement_attempted': enhanced_record.get('enhancement_attempted', False),
                            'enhancement_timestamp': enhanced_record.get('enhancement_timestamp'),
                            'pdf_analysis_data': enhanced_record.get('tier_2_pdf_analysis', {})
                        },
                        'what_information_involved_text': what_information_involved_text,  # Store for easy access
                        'pdf_analysis_summary': {
                            'affected_individuals_extracted': affected_individuals,
                            'what_information_involved_extracted': bool(what_information_involved_text),
                            'pdf_document_analyzed': enhanced_record.get('tier_2_pdf_analysis', {}).get('pdf_analyzed', False)
                        }
                    }
                }

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
                    if not enhancement_status['has_pdf_analysis'] and enhanced_record.get('tier_2_pdf_analysis', {}).get('pdf_analyzed'):
                        should_update = True
                        update_reasons.append("now has successful PDF analysis")

                    # Check if we now have affected individuals count when we didn't before
                    current_affected = enhancement_status.get('affected_individuals')
                    new_affected = db_item.get('affected_individuals')
                    if not current_affected and new_affected:
                        should_update = True
                        update_reasons.append("now has affected individuals count")

                    if should_update:
                        logger.info(f"Updating existing item for {enhanced_record['organization_name']}: {','.join(update_reasons)}")
                        update_success = supabase_client.update_item_enhancement(enhancement_status['item_id'], db_item)
                        if update_success:
                            logger.info(f"Successfully updated enhancement data for {enhanced_record['organization_name']}")
                            processed_count += 1
                        else:
                            logger.error(f"Failed to update enhancement data for {enhanced_record['organization_name']}")
                    else:
                        logger.debug(f"Skipping {enhanced_record['organization_name']} - already exists with adequate data")
                else:
                    # New item - insert it
                    insert_response = supabase_client.insert_item(**db_item)
                    if insert_response:
                        logger.info(f"Successfully inserted new item for {enhanced_record['organization_name']}")
                        processed_count += 1
                    else:
                        logger.error(f"Failed to insert item for {enhanced_record['organization_name']}")

            except Exception as e:
                logger.error(f"Error processing breach for '{breach_record.get('organization_name', 'Unknown')}': {e}", exc_info=True)
                continue

        logger.info(f"Finished processing Hawaii AG breaches. Total processed: {processed_count}/{total_breaches}")

    except Exception as e:
        logger.error(f"Critical error in Hawaii AG scraper: {e}", exc_info=True)

if __name__ == "__main__":
    logger.info("Hawaii AG Security Breach Scraper Started")

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_hawaii_ag_breaches()

    logger.info("Hawaii AG Security Breach Scraper Finished")
