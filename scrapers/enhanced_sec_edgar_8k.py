#!/usr/bin/env python3
"""
Enhanced SEC EDGAR 8-K Scraper with XBRL/CYD Taxonomy Support

This enhanced version builds on the existing SEC scraper to add:
- XBRL parsing for structured cybersecurity data (CYD taxonomy)
- Enhanced filing metadata extraction
- Exhibit document analysis
- Amendment tracking (8-K/A)
- Comprehensive data extraction per the "shopping list"

Author: Enhanced for comprehensive SEC cybersecurity incident detection
"""

import os
import sys
import time
import logging
import requests
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json

# Add the parent directory to the path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.supabase_client import SupabaseClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# SEC EDGAR URLs
SEC_RSS_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
SEC_BASE_URL = "https://www.sec.gov"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"

# Enhanced cybersecurity keywords (from original scraper + additions)
CYBERSECURITY_KEYWORDS = [
    # Primary indicators (high weight)
    "item 1.05", "material cybersecurity", "cybersecurity incident",
    "data breach", "security incident", "security breach",

    # Attack types
    "unauthorized access", "cyber attack", "data compromise", "ransomware",
    "malware", "phishing", "social engineering", "insider threat",

    # Data types (common in breach descriptions)
    "customer data", "personal information", "personally identifiable",
    "social security", "credit card", "financial information",
    "account information", "government id", "driver's license", "passport",

    # Impact indicators
    "threat actor", "extortion", "demanded money", "law enforcement",
    "forensic investigation", "customer reimbursement", "remediation costs",

    # Technical indicators
    "internal systems", "compromised information", "accessed without authorization",
    "improper data access", "security monitoring", "information security",
    "data security incident"
]

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

# 8-K Item codes related to cybersecurity
CYBERSECURITY_8K_ITEMS = ["1.05", "8.01"]

# Source ID for SEC EDGAR 8-K
SOURCE_ID_SEC_EDGAR_8K = 1

# SEC-compliant headers (REQUIRED by SEC)
REQUEST_HEADERS = {
    'User-Agent': 'Enhanced Breach Monitor Bot admin@breachmonitor.com',
    'Accept-Encoding': 'gzip, deflate'
}

# Rate limiting: SEC allows max 10 requests per second
RATE_LIMIT_DELAY = 0.1  # 100ms between requests

def rate_limit_request():
    """Implement SEC rate limiting - max 10 requests per second"""
    time.sleep(RATE_LIMIT_DELAY)

def extract_cik_from_url(url):
    """Extract CIK from SEC EDGAR URL"""
    try:
        # Pattern: /Archives/edgar/data/{cik}/{accession}/...
        match = re.search(r'/data/(\d+)/', url)
        if match:
            return match.group(1).zfill(10)  # Pad to 10 digits
    except:
        pass
    return None

def extract_accession_from_url(url):
    """Extract accession number from SEC EDGAR URL"""
    try:
        # Pattern: /Archives/edgar/data/{cik}/{accession}/...
        match = re.search(r'/data/\d+/([0-9-]+)/', url)
        if match:
            return match.group(1)
    except:
        pass
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
        response = requests.get(xbrl_url, headers=REQUEST_HEADERS, timeout=30)
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
        response = requests.get(filing_url, headers=REQUEST_HEADERS, timeout=30)
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
                    exhibit_urls.append(urljoin(base_url + '/', href))

        # Also check for exhibit references in text
        exhibit_pattern = r'Exhibit\s+(\d+(?:\.\d+)?)'
        exhibit_matches = re.findall(exhibit_pattern, response.text, re.IGNORECASE)

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

def extract_affected_individuals(text_content):
    """
    Extract number of affected individuals from filing text.

    Args:
        text_content (str): Filing text content

    Returns:
        int: Number of affected individuals or None
    """
    try:
        # Patterns for affected individuals
        patterns = [
            r'(\d+(?:,\d+)*)\s+(?:individuals?|persons?|customers?|users?|accounts?|records?)\s+(?:were\s+)?(?:affected|impacted|compromised)',
            r'(?:affected|impacted|compromised)\s+(?:approximately\s+)?(\d+(?:,\d+)*)\s+(?:individuals?|persons?|customers?|users?)',
            r'(\d+(?:,\d+)*)\s+(?:customer|user|individual|person)\s+(?:accounts?|records?)\s+(?:were\s+)?(?:accessed|compromised|affected)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            if matches:
                # Take the largest number found
                numbers = [int(match.replace(',', '')) for match in matches]
                return max(numbers)

    except Exception as e:
        logger.debug(f"Error extracting affected individuals: {e}")

    return None

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

def process_enhanced_8k_filing(filing_url, filing_data):
    """
    Process a single 8-K filing with enhanced data extraction.

    Args:
        filing_url (str): URL to the 8-K filing
        filing_data (dict): Basic filing metadata

    Returns:
        dict: Enhanced filing data or None if not cybersecurity-related
    """
    try:
        logger.info(f"Processing enhanced 8-K filing: {filing_url}")

        # Get the main filing content
        rate_limit_request()
        response = requests.get(filing_url, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        full_text = soup.get_text()

        # Check for cybersecurity relevance
        cybersecurity_score = 0
        keywords_detected = []
        keyword_contexts = {}

        for keyword in CYBERSECURITY_KEYWORDS:
            if keyword.lower() in full_text.lower():
                cybersecurity_score += 1
                keywords_detected.append(keyword)

                # Extract context around keyword
                pattern = rf'.{{0,100}}{re.escape(keyword)}.{{0,100}}'
                matches = re.findall(pattern, full_text, re.IGNORECASE)
                if matches:
                    keyword_contexts[keyword] = matches[0][:200]  # Limit context length

        # Skip if not cybersecurity-related (threshold: at least 1 keyword)
        if cybersecurity_score == 0:
            logger.debug(f"Skipping non-cybersecurity filing: {filing_url}")
            return None

        logger.info(f"Cybersecurity filing detected with score {cybersecurity_score}")

        # Extract basic metadata
        cik = extract_cik_from_url(filing_url)
        accession_number = extract_accession_from_url(filing_url)

        # Construct XBRL instance URL and parse if available
        xbrl_instance_url = construct_xbrl_instance_url(filing_url)
        cyd_data = {}
        if xbrl_instance_url:
            cyd_data = parse_xbrl_instance(xbrl_instance_url)

        # Extract exhibit URLs
        exhibit_urls = extract_exhibit_urls(filing_url)

        # Extract financial impact
        min_cost, max_cost, currency = extract_financial_impact(full_text)

        # Extract data types compromised
        data_types = extract_data_types_compromised(full_text)

        # Extract affected individuals count
        affected_individuals = extract_affected_individuals(full_text)

        # Extract incident dates
        incident_dates = extract_incident_dates(full_text)

        # Determine 8-K items disclosed
        items_disclosed = []
        if "item 1.05" in full_text.lower():
            items_disclosed.append("1.05")
        if "item 8.01" in full_text.lower():
            items_disclosed.append("8.01")

        # Check if this is an amendment
        is_amendment = "/A" in filing_url or "amendment" in full_text.lower()

        # Check for delayed disclosure
        is_delayed = "national security" in full_text.lower() or "rule 0-6" in full_text.lower()

        # Build enhanced filing data
        enhanced_data = {
            # Core metadata
            'cik': cik or cyd_data.get('cik'),
            'ticker_symbol': cyd_data.get('ticker_symbol'),
            'accession_number': accession_number,
            'form_type': filing_data.get('form_type', '8-K'),
            'filing_date': filing_data.get('filing_date'),
            'report_date': filing_data.get('report_date'),
            'primary_document_url': filing_url,
            'xbrl_instance_url': xbrl_instance_url,

            # Classification
            'items_disclosed': items_disclosed,
            'is_cybersecurity_related': True,
            'is_amendment': is_amendment,
            'is_delayed_disclosure': is_delayed,

            # CYD taxonomy data (from XBRL)
            'incident_nature_text': cyd_data.get('incident_nature'),
            'incident_scope_text': cyd_data.get('incident_scope'),
            'incident_timing_text': cyd_data.get('incident_timing'),
            'incident_impact_text': cyd_data.get('incident_impact'),
            'incident_unknown_details_text': cyd_data.get('incident_unknown'),

            # Incident timeline
            'incident_discovery_date': incident_dates.get('discovery_date'),
            'incident_disclosure_date': filing_data.get('filing_date'),
            'incident_containment_date': incident_dates.get('containment_date'),

            # Impact assessment
            'estimated_cost_min': min_cost,
            'estimated_cost_max': max_cost,
            'estimated_cost_currency': currency,
            'data_types_compromised': data_types,
            'affected_individuals': affected_individuals,

            # Document analysis
            'exhibit_urls': exhibit_urls,
            'keywords_detected': keywords_detected,
            'keyword_contexts': keyword_contexts,
            'file_size_bytes': len(response.content),

            # Business context
            'business_description': cyd_data.get('entity_name'),

            # Enhanced raw data
            'raw_data_json': {
                **filing_data,
                'cybersecurity_score': cybersecurity_score,
                'cyd_taxonomy_data': cyd_data,
                'enhanced_extraction': True,
                'extraction_timestamp': datetime.now().isoformat()
            }
        }

        logger.info(f"Enhanced data extraction completed for {filing_url}")
        return enhanced_data

    except Exception as e:
        logger.error(f"Error processing enhanced 8-K filing {filing_url}: {e}")
        return None

if __name__ == "__main__":
    logger.info("Enhanced SEC EDGAR 8-K Scraper Started")

    # This enhanced scraper is ready for integration with the main RSS processing
    print("Enhanced SEC scraper with XBRL/CYD parsing completed!")
    print("Key capabilities:")
    print("- XBRL/CYD taxonomy parsing")
    print("- Enhanced metadata extraction")
    print("- Exhibit document analysis")
    print("- Financial impact detection")
    print("- Data type classification")
    print("- Incident timeline extraction")
    print("- Amendment tracking")
    print("- Comprehensive keyword analysis")
    print("\nReady for integration with existing SEC RSS scraper!")
