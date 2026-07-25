import os
import logging
import requests
import re
import time
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json

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
SEC_BASE_URL = "https://www.sec.gov"
SEC_RSS_URL = f"{SEC_BASE_URL}/cgi-bin/browse-edgar"

# Enhanced cybersecurity keywords for comprehensive detection
CYBERSECURITY_KEYWORDS = [
    # Primary indicators (high weight)
    "item 1.05",
    "material cybersecurity",
    "cybersecurity incident",
    "data breach",
    "security incident",
    "security breach",

    # Attack types
    "unauthorized access",
    "cyber attack",
    "data compromise",
    "ransomware",
    "malware",
    "phishing",
    "social engineering",
    "insider threat",

    # Data types (common in breach descriptions)
    "customer data",
    "personal information",
    "personally identifiable",
    "social security",
    "credit card",
    "financial information",
    "account information",
    "government id",
    "driver's license",
    "passport",

    # Impact indicators
    "threat actor",
    "extortion",
    "demanded money",
    "law enforcement",
    "forensic investigation",
    "customer reimbursement",
    "remediation costs",

    # Technical indicators
    "internal systems",
    "compromised information",
    "accessed without authorization",
    "improper data access",
    "security monitoring",
    "information security",
    "data security incident"
]

# 8-K Item codes related to cybersecurity (Item 1.05 and 8.01 are common)
CYBERSECURITY_8K_ITEMS = ["1.05", "8.01"]

# CYD (Cybersecurity Disclosure) taxonomy tags for XBRL parsing
CYD_TAXONOMY_TAGS = {
    # Material Cybersecurity Incident tags (Item 1.05)
    "incident_nature": "MaterialCybersecurityIncidentNatureTextBlock",
    "incident_scope": "MaterialCybersecurityIncidentScopeTextBlock",
    "incident_timing": "MaterialCybersecurityIncidentTimingTextBlock",
    "incident_impact": "MaterialCybersecurityIncidentMaterialImpactOrReasonablyLikelyMaterialImpactTextBlock",
    "incident_unknown": "MaterialCybersecurityIncidentInformationNotAvailableOrUndeterminedTextBlock",

    # Risk Management tags (10-K/10-Q)
    "risk_processes": "CybersecurityRiskManagementProcessesForAssessingIdentifyingAndManagingThreatsTextBlock",
    "risk_board_oversight": "CybersecurityRiskBoardOfDirectorsOversightTextBlock",
    "risk_management_role": "CybersecurityRiskRoleOfManagementTextBlock",
}

# Source ID for SEC EDGAR 8-K
SOURCE_ID_SEC_EDGAR_8K = 1

# SEC-compliant headers (REQUIRED by SEC)
REQUEST_HEADERS = {
    'User-Agent': 'Breach Monitor Bot admin@breachmonitor.com',  # SEC requires proper identification
    'Accept-Encoding': 'gzip, deflate'
}

# Separate headers for different SEC endpoints
SEC_DATA_HEADERS = {
    'User-Agent': 'Breach Monitor Bot admin@breachmonitor.com',
    'Accept-Encoding': 'gzip, deflate',
    'Host': 'data.sec.gov'
}

SEC_WWW_HEADERS = {
    'User-Agent': 'Breach Monitor Bot admin@breachmonitor.com',
    'Accept-Encoding': 'gzip, deflate',
    'Host': 'www.sec.gov'
}

# Rate limiting: SEC allows max 10 requests per second
RATE_LIMIT_DELAY = 0.1  # 100ms between requests

def rate_limit_request():
    """Implement SEC rate limiting - max 10 requests per second"""
    time.sleep(RATE_LIMIT_DELAY)

def get_recent_8k_filings(days_back=1):
    """
    Get recent 8-K filings from SEC EDGAR using RSS feeds.
    This approach gets ALL recent 8-K filings, not just from specific companies.

    Args:
        days_back (int): Number of days back to search.

    Returns:
        list: List of 8-K filing metadata.
    """
    filings = []

    try:
        # Use SEC RSS feed for recent filings - gets ALL companies
        params = {
            "action": "getcurrent",
            "type": "8-K",
            "count": "200",  # Get more filings to catch cybersecurity incidents
            "output": "atom"
        }

        logger.info("Fetching recent 8-K filings from SEC RSS feed...")

        rate_limit_request()
        response = requests.get(SEC_RSS_URL, params=params, headers=SEC_WWW_HEADERS, timeout=30)
        response.raise_for_status()

        # Parse RSS/Atom feed
        try:
            root = ET.fromstring(response.text)

            # Find entries in the feed
            entries = root.findall('.//{http://www.w3.org/2005/Atom}entry')

            logger.info(f"Found {len(entries)} recent 8-K filings")

            for entry in entries:
                try:
                    # Extract filing information
                    title = entry.find('.//{http://www.w3.org/2005/Atom}title')
                    link = entry.find('.//{http://www.w3.org/2005/Atom}link')
                    updated = entry.find('.//{http://www.w3.org/2005/Atom}updated')
                    summary = entry.find('.//{http://www.w3.org/2005/Atom}summary')

                    if title is not None and link is not None:
                        filing_info = {
                            "title": title.text if title.text else "",
                            "document_url": link.get('href', ''),
                            "filing_date": updated.text if updated is not None else "",
                            "summary": summary.text if summary is not None else "",
                            "form_type": "8-K"
                        }

                        # Extract company name and additional metadata from title
                        title_text = filing_info["title"]
                        if " - " in title_text:
                            company_part = title_text.split(" - ")[0]
                            filing_info["company_name"] = company_part.strip()

                        # Extract CIK, ticker, and other metadata from summary if available
                        summary_text = filing_info.get("summary", "")
                        if summary_text:
                            # Extract CIK (Central Index Key)
                            import re
                            cik_match = re.search(r'CIK:\s*(\d+)', summary_text)
                            if cik_match:
                                filing_info["cik"] = cik_match.group(1).zfill(10)  # Pad to 10 digits

                            # Extract accession number
                            accession_match = re.search(r'Accession Number:\s*([0-9-]+)', summary_text)
                            if accession_match:
                                filing_info["accession_number"] = accession_match.group(1)

                            # Extract file size
                            size_match = re.search(r'Size:\s*(\d+)', summary_text)
                            if size_match:
                                filing_info["file_size"] = int(size_match.group(1))

                        # Extract additional metadata from document URL
                        doc_url = filing_info.get("document_url", "")
                        if doc_url:
                            # Extract accession number from URL if not found in summary
                            if "accession_number" not in filing_info:
                                url_accession_match = re.search(r'/([0-9-]+)/', doc_url)
                                if url_accession_match:
                                    filing_info["accession_number"] = url_accession_match.group(1)

                            # Extract primary document name
                            primary_doc_match = re.search(r'/([^/]+\.htm?)$', doc_url)
                            if primary_doc_match:
                                filing_info["primary_document"] = primary_doc_match.group(1)

                        # Check if filing is recent
                        if is_recent_filing(filing_info.get("filing_date", ""), days_back):
                            filings.append(filing_info)

                except Exception as entry_error:
                    logger.warning(f"Error processing RSS entry: {entry_error}")
                    continue

        except ET.ParseError as parse_error:
            logger.error(f"Failed to parse RSS feed: {parse_error}")
            # Fallback to HTML parsing
            filings = get_8k_filings_html_fallback(response.text, days_back)

    except Exception as e:
        logger.error(f"Error fetching 8-K filings: {e}")

    return filings

def get_8k_filings_html_fallback(html_content, days_back):
    """Fallback method to parse 8-K filings from HTML."""
    filings = []

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Look for filing entries in the HTML
        filing_rows = soup.find_all('tr')

        for row in filing_rows[:50]:  # Limit to recent filings
            cells = row.find_all('td')
            if len(cells) >= 4:
                # Extract filing information from table cells
                filing_info = {
                    "company_name": cells[0].get_text(strip=True) if cells[0] else "",
                    "form_type": cells[1].get_text(strip=True) if cells[1] else "",
                    "filing_date": cells[2].get_text(strip=True) if cells[2] else "",
                    "document_url": ""
                }

                # Look for document link
                link = row.find('a')
                if link and link.get('href'):
                    filing_info["document_url"] = f"{SEC_BASE_URL}{link['href']}"

                if filing_info["form_type"] == "8-K" and is_recent_filing(filing_info["filing_date"], days_back):
                    filings.append(filing_info)

    except Exception as e:
        logger.error(f"Error in HTML fallback: {e}")

    return filings

def is_recent_filing(date_str, days_back):
    """Check if a filing date is recent."""
    if not date_str:
        return True  # If no date, assume recent

    try:
        # Parse various date formats from SEC
        filing_date = None

        if 'T' in date_str:
            # ISO format with time
            filing_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
        elif '-' in date_str and len(date_str) >= 10:
            # YYYY-MM-DD format
            filing_date = datetime.strptime(date_str[:10], '%Y-%m-%d').date()
        else:
            # Try other common formats
            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']:
                try:
                    filing_date = datetime.strptime(date_str, fmt).date()
                    break
                except:
                    continue

        if filing_date:
            cutoff_date = (datetime.now() - timedelta(days=days_back)).date()
            is_recent = filing_date >= cutoff_date
            logger.debug(f"Date check: {date_str} -> {filing_date} >= {cutoff_date} = {is_recent}")
            return is_recent
        else:
            logger.warning(f"Could not parse date: {date_str}")
            return True  # If parsing fails, assume recent

    except Exception as e:
        logger.warning(f"Error parsing date '{date_str}': {e}")
        return True  # If parsing fails, assume recent

def extract_filing_content(document_url):
    """
    Extract full text content from an 8-K filing.

    Args:
        document_url (str): URL to the SEC filing document.

    Returns:
        dict: Extracted content and metadata.
    """
    content_data = {}

    try:
        logger.info(f"Extracting content from: {document_url}")

        rate_limit_request()
        response = requests.get(document_url, headers=SEC_WWW_HEADERS, timeout=30)

        if not response.ok:
            logger.warning(f"Failed to fetch document: {response.status_code}")
            return content_data

        # Parse the SEC filing format
        text_content = response.text

        # Extract different sections
        content_data["full_text"] = text_content
        content_data["text_length"] = len(text_content)

        # Look for specific cybersecurity sections
        cyber_sections = extract_cybersecurity_sections(text_content)
        content_data.update(cyber_sections)

        # Extract business description and other metadata
        metadata = extract_filing_metadata(text_content)
        content_data.update(metadata)

        logger.info(f"Extracted {len(content_data)} content fields")

    except Exception as e:
        logger.error(f"Error extracting filing content: {e}")

    return content_data

def extract_cybersecurity_sections(text_content):
    """
    Extract cybersecurity-specific sections from 8-K filing.

    Args:
        text_content (str): Full text of the filing.

    Returns:
        dict: Extracted cybersecurity information.
    """
    cyber_data = {}

    try:
        # Check if this is a cybersecurity-related filing with context extraction
        cyber_score = 0
        found_keywords = []
        keyword_contexts = []

        # Extract context around each keyword match
        for keyword in CYBERSECURITY_KEYWORDS:
            if keyword.lower() in text_content.lower():
                cyber_score += 1
                found_keywords.append(keyword)

                # Extract context around this keyword
                contexts = extract_keyword_context(text_content, keyword)
                for context in contexts:
                    keyword_contexts.append({
                        "keyword": keyword,
                        "context": context["context"],
                        "position": context["position"],
                        "before_words": context["before_words"],
                        "after_words": context["after_words"]
                    })

        cyber_data["cybersecurity_keyword_count"] = cyber_score
        cyber_data["cybersecurity_keywords_found"] = found_keywords[:10]  # First 10
        cyber_data["keyword_contexts"] = keyword_contexts[:20]  # First 20 contexts

        # Special case: if "item 1.05" is found, it's definitely cybersecurity
        has_item_105 = "item 1.05" in text_content.lower()
        cyber_data["is_cybersecurity_related"] = has_item_105 or cyber_score >= 1

        if cyber_score >= 2:
            # Extract Item 1.05 section (Material Cybersecurity Incidents)
            item_105_pattern = r"item\s+1\.05[^a-z]*?([^<]*?)(?=item\s+\d|signature|</text>)"
            item_105_match = re.search(item_105_pattern, text_content, re.IGNORECASE | re.DOTALL)

            if item_105_match:
                cyber_data["item_105_content"] = item_105_match.group(1).strip()[:2000]  # Limit length

            # Extract incident description patterns
            incident_patterns = [
                r"(?:incident|breach|attack)\s+(?:description|details?):\s*([^.]{100,500})",
                r"(?:on|around)\s+([A-Za-z]+ \d{1,2},? \d{4})[^.]*(?:incident|breach|attack)",
                r"(?:affecting|involving)\s+(?:approximately\s+)?(\d+(?:,\d+)*)\s+(?:individuals?|customers?|records?)",
                r"(?:types?\s+of\s+)?(?:information|data)\s+(?:involved|affected|compromised):\s*([^.]{50,300})"
            ]

            for i, pattern in enumerate(incident_patterns):
                match = re.search(pattern, text_content, re.IGNORECASE | re.DOTALL)
                if match:
                    cyber_data[f"incident_detail_{i+1}"] = match.group(1).strip()[:300]

            # Extract dates mentioned in the filing
            date_pattern = r'([A-Za-z]+ \d{1,2},? \d{4})'
            dates_found = re.findall(date_pattern, text_content)
            if dates_found:
                cyber_data["dates_mentioned"] = list(set(dates_found))[:10]  # First 10 unique dates

    except Exception as e:
        logger.error(f"Error extracting cybersecurity sections: {e}")

    return cyber_data

def extract_keyword_context(text_content, keyword, context_words=10):
    """
    Extract context around keyword matches (10 words before and after).

    Args:
        text_content (str): Full text content to search
        keyword (str): Keyword to find
        context_words (int): Number of words before and after to extract

    Returns:
        list: List of context dictionaries for each match
    """
    contexts = []

    try:
        # Clean text for better word splitting
        clean_text = re.sub(r'<[^>]+>', ' ', text_content)  # Remove HTML tags
        clean_text = re.sub(r'\s+', ' ', clean_text)  # Normalize whitespace

        # Split into words
        words = clean_text.split()

        # Find all occurrences of the keyword
        keyword_lower = keyword.lower()

        for i, word in enumerate(words):
            # Check if this word (or sequence of words) matches the keyword
            if keyword_lower in ' '.join(words[i:i+len(keyword.split())]).lower():
                # Calculate context boundaries
                start_idx = max(0, i - context_words)
                end_idx = min(len(words), i + len(keyword.split()) + context_words)

                # Extract before and after words
                before_words = words[start_idx:i]
                keyword_words = words[i:i+len(keyword.split())]
                after_words = words[i+len(keyword.split()):end_idx]

                # Create context string
                context_text = ' '.join(before_words + ['**' + ' '.join(keyword_words) + '**'] + after_words)

                context_info = {
                    "context": context_text[:500],  # Limit length
                    "position": i,
                    "before_words": ' '.join(before_words[-context_words:]),  # Last N words before
                    "after_words": ' '.join(after_words[:context_words])      # First N words after
                }

                contexts.append(context_info)

                # Limit to 5 contexts per keyword to avoid overwhelming data
                if len(contexts) >= 5:
                    break

    except Exception as e:
        logger.error(f"Error extracting context for '{keyword}': {e}")

    return contexts

def extract_filing_metadata(text_content):
    """
    Extract general metadata from the filing.

    Args:
        text_content (str): Full text of the filing.

    Returns:
        dict: Extracted metadata.
    """
    metadata = {}

    try:
        # Extract business description
        business_pattern = r"business\s+(?:description|overview):\s*([^<]{200,1000})"
        business_match = re.search(business_pattern, text_content, re.IGNORECASE | re.DOTALL)
        if business_match:
            metadata["business_description"] = business_match.group(1).strip()[:500]

        # Extract industry information
        industry_pattern = r"(?:industry|sector|business):\s*([^<]{50,200})"
        industry_match = re.search(industry_pattern, text_content, re.IGNORECASE)
        if industry_match:
            metadata["industry_description"] = industry_match.group(1).strip()[:200]

        # Extract filing date from content
        filing_date_pattern = r"filing\s+date:\s*(\d{4}-\d{2}-\d{2})"
        filing_date_match = re.search(filing_date_pattern, text_content, re.IGNORECASE)
        if filing_date_match:
            metadata["content_filing_date"] = filing_date_match.group(1)

    except Exception as e:
        logger.error(f"Error extracting filing metadata: {e}")

    return metadata

def extract_affected_individuals_from_content(text_content: str) -> int | None:
    """
    Extract the number of affected individuals from SEC filing content.

    Args:
        text_content (str): Full text of the filing.

    Returns:
        int | None: Number of affected individuals or None if not found.
    """
    if not text_content:
        return None

    try:
        # Common patterns for affected individuals in SEC filings
        patterns = [
            r'(?:affecting|involving|impacting)\s+(?:approximately\s+)?(\d+(?:,\d+)*)\s+(?:individuals?|customers?|users?|people|persons)',
            r'(\d+(?:,\d+)*)\s+(?:individuals?|customers?|users?|people|persons)\s+(?:were\s+)?(?:affected|impacted|involved)',
            r'(?:data\s+of\s+)?(?:approximately\s+)?(\d+(?:,\d+)*)\s+(?:individuals?|customers?|users?)',
            r'(?:personal\s+information\s+of\s+)?(?:approximately\s+)?(\d+(?:,\d+)*)\s+(?:individuals?|customers?)',
            r'breach\s+(?:affecting|involving)\s+(?:approximately\s+)?(\d+(?:,\d+)*)',
            r'incident\s+(?:affecting|involving)\s+(?:approximately\s+)?(\d+(?:,\d+)*)'
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            if matches:
                # Take the first match and convert to integer
                number_str = matches[0].replace(',', '')
                try:
                    return int(number_str)
                except ValueError:
                    continue

    except Exception as e:
        logger.error(f"Error extracting affected individuals: {e}")

    return None

def construct_xbrl_instance_url(filing_url):
    """Construct XBRL instance URL from main filing URL"""
    try:
        # Convert main filing URL to XBRL instance URL
        # Example: coin-20250514.htm -> coin-20250514_htm.xml
        if filing_url.endswith('.htm'):
            base_url = filing_url.rsplit('/', 1)[0]
            filename = filing_url.rsplit('/', 1)[1]
            xbrl_filename = filename.replace('.htm', '_htm.xml')
            return f"{base_url}/{xbrl_filename}"
    except:
        pass
    return None

def parse_xbrl_instance(xbrl_url):
    """
    Parse XBRL instance document to extract CYD taxonomy data.

    Args:
        xbrl_url (str): URL to XBRL instance document

    Returns:
        dict: Extracted CYD taxonomy data
    """
    cyd_data = {}

    try:
        rate_limit_request()
        response = requests.get(xbrl_url, headers=SEC_WWW_HEADERS, timeout=30)
        response.raise_for_status()

        # Parse XML
        root = ET.fromstring(response.content)

        # Define namespaces
        namespaces = {
            'cyd': 'http://xbrl.sec.gov/cyd/2024',
            'dei': 'http://xbrl.sec.gov/dei/2024',
            'xbrli': 'http://www.xbrl.org/2003/instance'
        }

        # Extract CYD taxonomy data
        for key, tag_name in CYD_TAXONOMY_TAGS.items():
            try:
                element = root.find(f'.//cyd:{tag_name}', namespaces)
                if element is not None:
                    # Clean up HTML content and extract text
                    text_content = element.text or ""
                    if text_content:
                        # Remove HTML tags and clean up
                        clean_text = re.sub(r'<[^>]+>', '', text_content)
                        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                        cyd_data[key] = clean_text[:2000]  # Limit length
            except Exception as e:
                logger.debug(f"Error extracting {tag_name}: {e}")

        # Extract additional metadata from DEI namespace
        try:
            cik_element = root.find('.//dei:EntityCentralIndexKey', namespaces)
            if cik_element is not None:
                cyd_data['cik'] = cik_element.text

            ticker_element = root.find('.//dei:TradingSymbol', namespaces)
            if ticker_element is not None:
                cyd_data['ticker_symbol'] = ticker_element.text

            entity_name_element = root.find('.//dei:EntityRegistrantName', namespaces)
            if entity_name_element is not None:
                cyd_data['entity_name'] = entity_name_element.text

        except Exception as e:
            logger.debug(f"Error extracting DEI metadata: {e}")

        logger.info(f"Extracted {len(cyd_data)} CYD taxonomy fields from XBRL")

    except Exception as e:
        logger.error(f"Error parsing XBRL instance {xbrl_url}: {e}")

    return cyd_data

def extract_exhibit_urls(filing_url):
    """
    Extract exhibit URLs from SEC filing.

    Args:
        filing_url (str): URL to main SEC filing

    Returns:
        list: List of exhibit URLs
    """
    exhibit_urls = []

    try:
        # Get the filing directory URL
        base_url = filing_url.rsplit('/', 1)[0]

        rate_limit_request()
        response = requests.get(filing_url, headers=SEC_WWW_HEADERS, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Look for exhibit links in the filing
        # Pattern: EX-99.1, EX-99.2, etc.
        exhibit_links = soup.find_all('a', href=re.compile(r'.*ex.*\.htm', re.IGNORECASE))

        for link in exhibit_links:
            href = link.get('href')
            if href:
                if href.startswith('http'):
                    exhibit_urls.append(href)
                else:
                    from urllib.parse import urljoin
                    exhibit_urls.append(urljoin(base_url + '/', href))

        logger.info(f"Found {len(exhibit_urls)} exhibit URLs")

    except Exception as e:
        logger.error(f"Error extracting exhibit URLs: {e}")

    return exhibit_urls[:10]  # Limit to first 10 exhibits

def extract_financial_impact(text_content):
    """
    Extract financial impact estimates from filing text.

    Args:
        text_content (str): Filing text content

    Returns:
        tuple: (min_cost, max_cost, currency)
    """
    try:
        # Pattern for dollar amounts: $X million, $X.X billion, etc.
        money_pattern = r'\$\s*(\d+(?:\.\d+)?)\s*(million|billion|thousand)?'
        matches = re.findall(money_pattern, text_content, re.IGNORECASE)

        amounts = []
        for amount_str, unit in matches:
            try:
                amount = float(amount_str)
                if unit.lower() == 'billion':
                    amount *= 1_000_000_000
                elif unit.lower() == 'million':
                    amount *= 1_000_000
                elif unit.lower() == 'thousand':
                    amount *= 1_000
                amounts.append(amount)
            except:
                continue

        if amounts:
            return min(amounts), max(amounts), 'USD'

    except Exception as e:
        logger.debug(f"Error extracting financial impact: {e}")

    return None, None, None

def extract_data_types_compromised(text_content):
    """
    Extract types of data compromised from filing text.

    Args:
        text_content (str): Filing text content

    Returns:
        list: List of data types compromised
    """
    data_types = []

    # Common data type patterns
    data_type_patterns = {
        'PII': r'personal(?:ly)?\s+identif(?:iable|ying)\s+information|PII',
        'SSN': r'social\s+security\s+number|SSN',
        'Credit Card': r'credit\s+card|payment\s+card|card\s+data',
        'Financial': r'financial\s+information|bank\s+account|account\s+number',
        'PHI': r'protected\s+health\s+information|PHI|medical\s+record',
        'Government ID': r'driver\'?s?\s+license|passport|government\s+id',
        'Email': r'email\s+address',
        'Phone': r'phone\s+number|telephone',
        'Address': r'home\s+address|mailing\s+address',
        'Account Data': r'account\s+data|user\s+account|login\s+credential'
    }

    try:
        for data_type, pattern in data_type_patterns.items():
            if re.search(pattern, text_content, re.IGNORECASE):
                data_types.append(data_type)

    except Exception as e:
        logger.debug(f"Error extracting data types: {e}")

    return data_types

def extract_incident_dates(text_content):
    """
    Extract incident-related dates from filing text.

    Args:
        text_content (str): Filing text content

    Returns:
        dict: Dictionary with discovery_date, containment_date, etc.
    """
    dates = {}

    try:
        # Patterns for different types of dates
        date_patterns = {
            'discovery_date': [
                r'discovered\s+on\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
                r'became\s+aware\s+on\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
                r'identified\s+on\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})'
            ],
            'containment_date': [
                r'contained\s+on\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
                r'secured\s+on\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
                r'remediated\s+on\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})'
            ]
        }

        for date_type, patterns in date_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                if matches:
                    try:
                        # Parse the first match
                        date_str = matches[0]
                        parsed_date = datetime.strptime(date_str, '%B %d, %Y').date()
                        dates[date_type] = parsed_date.isoformat()
                        break
                    except:
                        continue

    except Exception as e:
        logger.debug(f"Error extracting incident dates: {e}")

    return dates

def search_text_for_keywords(text: str, keywords: list) -> list:
    """Searches text for keywords (case-insensitive) and returns found keywords."""
    if not text:
        return []
    found_keywords = []
    text_lower = text.lower()
    for keyword in keywords:
        if keyword.lower() in text_lower:
            found_keywords.append(keyword)
    return found_keywords

def fetch_filing_document_content(cik: str, accession_number: str, primary_document: str) -> tuple[str | None, str | None]:
    """
    Fetch the actual 8-K document content using SEC EDGAR URLs.
    Returns (document_url, document_text).
    """
    try:
        # Construct the document URL using SEC's standard path structure
        # Format: https://www.sec.gov/Archives/edgar/data/{cik}/{accession_number_no_dashes}/{primary_document}
        accession_no_dashes = accession_number.replace('-', '')
        document_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_no_dashes}/{primary_document}"

        rate_limit_request()
        response = requests.get(document_url, headers=SEC_WWW_HEADERS, timeout=30)
        response.raise_for_status()

        # Parse HTML content to extract text
        if primary_document.endswith(('.htm', '.html')):
            soup = BeautifulSoup(response.content, 'html.parser')
            document_text = soup.get_text(separator='\n', strip=True)
        else:
            document_text = response.text

        return document_url, document_text

    except Exception as e:
        logger.error(f"Error fetching document content for CIK {cik}, accession {accession_number}: {e}")
        return None, None

def is_cybersecurity_related(filing_info: dict, document_text: str = None) -> tuple[bool, list, str]:
    """
    Determine if a filing is cybersecurity-related based on items and content.
    Returns (is_related, found_keywords, reason).
    """
    found_keywords = []
    reasons = []

    # Check 8-K items first (faster than text search)
    items = filing_info.get('items', '')
    if items:
        for cyber_item in CYBERSECURITY_8K_ITEMS:
            if cyber_item in items:
                reasons.append(f"8-K Item {cyber_item}")
                found_keywords.append(f"item_{cyber_item}")

    # Search document text for cybersecurity keywords
    if document_text:
        text_keywords = search_text_for_keywords(document_text, CYBERSECURITY_KEYWORDS)
        if text_keywords:
            found_keywords.extend(text_keywords)
            reasons.append(f"Keywords: {', '.join(text_keywords[:3])}")  # Show first 3

    is_related = len(found_keywords) > 0
    reason = "; ".join(reasons) if reasons else "No cybersecurity indicators found"

    return is_related, found_keywords, reason

def process_edgar_filings():
    """
    Process recent SEC EDGAR 8-K filings using RSS feed approach.
    Gets ALL recent 8-K filings and analyzes them for cybersecurity content.
    """
    logger.info("Starting SEC EDGAR 8-K processing using RSS feed...")

    # Initialize Supabase client
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return

    # Get recent 8-K filings from ALL companies using RSS feed
    logger.info("Fetching recent 8-K filings from SEC RSS feed...")
    recent_filings = get_recent_8k_filings(days_back=7)  # Get last 7 days of filings

    if not recent_filings:
        logger.warning("No recent 8-K filings found")
        return

    logger.info(f"Found {len(recent_filings)} recent 8-K filings to analyze")

    total_processed = 0
    total_inserted = 0
    cybersecurity_found = 0

    for filing in recent_filings:
        try:
            company_name = filing.get("company_name", "Unknown Company")
            logger.info(f"Processing {company_name}")

            total_processed += 1

            # Extract full content from the filing
            content_data = extract_filing_content(filing.get("document_url", ""))

            if not content_data.get("full_text"):
                logger.warning(f"Could not fetch document content for {company_name}")
                continue

            # Analyze for cybersecurity content
            cyber_data = content_data
            is_cybersecurity = cyber_data.get("is_cybersecurity_related", False)
            found_keywords = cyber_data.get("cybersecurity_keywords_found", [])

            # ENHANCED: Add XBRL/CYD taxonomy parsing for structured data
            cyd_data = {}
            xbrl_instance_url = None
            exhibit_urls = []
            financial_impact = (None, None, None)
            data_types = []
            incident_dates = {}

            if is_cybersecurity:
                # Try to extract XBRL data for enhanced structured information
                filing_url = filing.get("document_url", "")
                xbrl_instance_url = construct_xbrl_instance_url(filing_url)

                if xbrl_instance_url:
                    logger.info(f"Attempting XBRL parsing for {company_name}")
                    cyd_data = parse_xbrl_instance(xbrl_instance_url)

                # Extract exhibit URLs for additional context
                exhibit_urls = extract_exhibit_urls(filing_url)

                # Extract financial impact estimates
                full_text = content_data.get("full_text", "")
                financial_impact = extract_financial_impact(full_text)

                # Extract data types compromised
                data_types = extract_data_types_compromised(full_text)

                # Extract incident timeline dates
                incident_dates = extract_incident_dates(full_text)

            if is_cybersecurity:
                cybersecurity_found += 1
                logger.info(f"Cybersecurity filing found: {company_name}")

                # Create summary snippet from cybersecurity context
                summary_snippet = f"Cybersecurity-related 8-K filing from {company_name}."

                # Get context from keyword analysis
                keyword_contexts = cyber_data.get("keyword_contexts", [])
                if keyword_contexts:
                    # Use the first context as summary
                    first_context = keyword_contexts[0]["context"]
                    summary_snippet = f"...{first_context[:300]}..."

                # Extract structured data for dedicated fields
                filing_date_only = None
                if filing.get("filing_date"):
                    try:
                        filing_date_only = filing["filing_date"][:10]  # Extract YYYY-MM-DD
                    except:
                        filing_date_only = filing.get("filing_date")

                # Extract affected individuals count from cybersecurity content
                affected_individuals = extract_affected_individuals_from_content(content_data.get("full_text", ""))

                # Prepare data for insertion with ENHANCED SEC-SPECIFIC FIELDS
                item_data = {
                    "source_id": SOURCE_ID_SEC_EDGAR_8K,
                    "item_url": filing.get("document_url", ""),
                    "title": f"SEC 8-K: {company_name} - Cybersecurity Filing",  # Enhanced title
                    "publication_date": filing.get("filing_date", datetime.now().isoformat()),
                    "summary_text": summary_snippet,

                    # STANDARDIZED CROSS-PORTAL FIELDS (aligned with Delaware AG, California AG, etc.)
                    "affected_individuals": affected_individuals,  # Number of people affected (consistent across all portals)
                    "breach_date": incident_dates.get('discovery_date') or filing_date_only,  # When incident occurred
                    "reported_date": filing_date_only,  # When reported to authority (SEC filing date)
                    "notice_document_url": filing.get("document_url", ""),  # Link to official notice document

                    # ENHANCED SEC-SPECIFIC FIELDS (using new database schema)
                    "cik": filing.get("cik") or cyd_data.get('cik'),
                    "ticker_symbol": cyd_data.get('ticker_symbol'),
                    "accession_number": filing.get("accession_number"),
                    "form_type": filing.get("form_type", "8-K"),
                    "filing_date": filing_date_only,
                    "report_date": filing_date_only,
                    "primary_document_url": filing.get("document_url"),
                    "xbrl_instance_url": xbrl_instance_url,

                    # Filing Classification
                    "items_disclosed": [item for item in CYBERSECURITY_8K_ITEMS if item in filing.get("items", "")],
                    "is_cybersecurity_related": True,
                    "is_amendment": "/A" in filing.get("document_url", ""),
                    "is_delayed_disclosure": "national security" in content_data.get("full_text", "").lower(),

                    # CYD Taxonomy Data (from XBRL)
                    "incident_nature_text": cyd_data.get('incident_nature'),
                    "incident_scope_text": cyd_data.get('incident_scope'),
                    "incident_timing_text": cyd_data.get('incident_timing'),
                    "incident_impact_text": cyd_data.get('incident_impact'),
                    "incident_unknown_details_text": cyd_data.get('incident_unknown'),

                    # Incident Timeline
                    "incident_discovery_date": incident_dates.get('discovery_date'),
                    "incident_disclosure_date": filing_date_only,
                    "incident_containment_date": incident_dates.get('containment_date'),

                    # Impact Assessment
                    "estimated_cost_min": financial_impact[0],
                    "estimated_cost_max": financial_impact[1],
                    "estimated_cost_currency": financial_impact[2],
                    "data_types_compromised": data_types,

                    # Document Analysis
                    "exhibit_urls": exhibit_urls,
                    "keywords_detected": found_keywords,
                    "keyword_contexts": {kw: ctx.get("context", "") for ctx in cyber_data.get("keyword_contexts", []) for kw in [ctx.get("keyword")] if kw},
                    "file_size_bytes": filing.get("file_size"),

                    # Business Context
                    "business_description": cyd_data.get('entity_name') or cyber_data.get("business_description"),
                    "industry_classification": cyber_data.get("industry_description"),

                    # Enhanced raw data with SEC-specific information (following portal standards)
                    "raw_data_json": {
                        # STANDARDIZED FIELDS (consistent with other portals)
                        "organization_name": company_name,  # Matches Delaware AG format
                        "filing_date": filing.get("filing_date", ""),  # Original date string
                        "reported_date": filing.get("filing_date", ""),  # When reported to SEC
                        "affected_individuals_extracted": affected_individuals,  # Parsed count
                        "notice_document_link": filing.get("document_url", ""),  # Official document

                        # SEC-SPECIFIC FIELDS (Enhanced)
                        "cik": filing.get("cik", "") or cyd_data.get('cik', ""),  # Central Index Key
                        "ticker_symbol": cyd_data.get('ticker_symbol', ""),  # Stock ticker from XBRL
                        "accession_number": filing.get("accession_number", ""),  # Unique filing ID
                        "form_type": filing.get("form_type", "8-K"),  # SEC form type
                        "items_disclosed": filing.get("items", ""),  # 8-K items (1.05, 8.01, etc.)
                        "file_size_bytes": filing.get("file_size", 0),  # Document size
                        "primary_document_filename": filing.get("primary_document", ""),  # Main file
                        "xbrl_instance_url": xbrl_instance_url,  # XBRL document URL

                        # ENHANCED XBRL/CYD TAXONOMY DATA
                        "cyd_taxonomy_data": cyd_data,  # Complete CYD taxonomy extraction
                        "incident_nature_structured": cyd_data.get('incident_nature', ""),
                        "incident_scope_structured": cyd_data.get('incident_scope', ""),
                        "incident_timing_structured": cyd_data.get('incident_timing', ""),
                        "incident_impact_structured": cyd_data.get('incident_impact', ""),
                        "incident_unknown_structured": cyd_data.get('incident_unknown', ""),

                        # ENHANCED IMPACT ANALYSIS
                        "financial_impact_min": financial_impact[0],
                        "financial_impact_max": financial_impact[1],
                        "financial_impact_currency": financial_impact[2],
                        "data_types_compromised": data_types,
                        "incident_timeline": incident_dates,

                        # ENHANCED DOCUMENT ANALYSIS
                        "exhibit_urls": exhibit_urls,
                        "exhibit_count": len(exhibit_urls),

                        # CYBERSECURITY ANALYSIS RESULTS (Enhanced)
                        "keywords_detected": found_keywords,  # All keywords found
                        "cybersecurity_keyword_count": cyber_data.get("cybersecurity_keyword_count", 0),
                        "cybersecurity_detection_reason": f"8-K Item {filing.get('items', '')}; Keywords: {', '.join(found_keywords[:3])}",
                        "keyword_contexts": cyber_data.get("keyword_contexts", [])[:5],  # Context around keywords
                        "item_105_content_extract": cyber_data.get("item_105_content", ""),  # Material cybersecurity incidents
                        "incident_dates_mentioned": cyber_data.get("dates_mentioned", []),  # Dates found in filing

                        # BUSINESS CONTEXT (Enhanced)
                        "business_description": cyd_data.get('entity_name') or cyber_data.get("business_description", ""),
                        "industry_classification": cyber_data.get("industry_description", ""),
                        "entity_name_from_xbrl": cyd_data.get('entity_name', ""),

                        # METADATA (Enhanced)
                        "source_portal": "SEC EDGAR",
                        "data_extraction_method": "RSS feed + content analysis + XBRL/CYD parsing",
                        "enhanced_extraction": True,
                        "extraction_timestamp": datetime.now().isoformat(),
                        "xbrl_parsing_successful": len(cyd_data) > 0,
                        "enhancement_version": "2.0"
                    },
                    "tags_keywords": ["sec_filing", "8-k", "cybersecurity"] + [kw.lower().replace(" ", "_") for kw in found_keywords[:5]]
                }

                # Insert into database
                try:
                    insert_response = supabase_client.insert_item(**item_data)
                    if insert_response:
                        logger.info(f"Successfully inserted cybersecurity filing for {company_name}")
                        total_inserted += 1
                    else:
                        logger.error(f"Failed to insert filing for {company_name}")
                except Exception as e:
                    if "duplicate key value violates unique constraint" in str(e):
                        logger.info(f"Filing already exists for {company_name}")
                    else:
                        logger.error(f"Error inserting filing: {e}")
            else:
                logger.debug(f"No cybersecurity content found in {company_name} filing")

        except Exception as e:
            logger.error(f"Error processing filing for {company_name}: {e}", exc_info=True)

    logger.info(f"SEC EDGAR processing complete:")
    logger.info(f"Total filings processed: {total_processed}")
    logger.info(f"Cybersecurity filings found: {cybersecurity_found}")
    logger.info(f"Successfully inserted: {total_inserted}")

if __name__ == "__main__":
    logger.info("SEC EDGAR 8-K Scraper Started")

    # Check for Supabase environment variables
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
        # Optionally, exit if critical env vars are missing
        # sys.exit(1)
    else:
        logger.info("Supabase environment variables seem to be set.")

    process_edgar_filings()
    logger.info("SEC EDGAR 8-K Scraper Finished")
