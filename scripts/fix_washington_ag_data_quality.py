#!/usr/bin/env python3
"""
Data Quality Fix Script for Washington AG Records

This script fixes data quality issues in existing Washington AG breach records by
re-scraping the current website data and updating the database records with
proper field values.

The current scraper works perfectly, but existing records were created with
an older version that didn't extract the rich data properly.
"""

import os
import sys
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Add the parent directory to the path so we can import from utils and scrapers
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.supabase_client import SupabaseClient
from scrapers.fetch_washington_ag import (
    WASHINGTON_AG_BREACH_URL, REQUEST_HEADERS, REQUEST_TIMEOUT,
    extract_pdf_url_wa, parse_affected_individuals_wa, 
    parse_date_flexible_wa, parse_data_types_compromised_wa,
    parse_date_to_date_only
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def scrape_current_washington_data():
    """
    Scrape the current Washington AG website to get fresh data.
    Returns a dictionary mapping organization names to their data.
    """
    logger.info("Scraping current Washington AG website data...")
    
    try:
        response = requests.get(WASHINGTON_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Washington AG page: {e}")
        return {}

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find the main data table
    data_table = soup.find('table')
    if not data_table:
        logger.error("No table found on the page")
        return {}
    
    tbody = data_table.find('tbody')
    if not tbody:
        notifications = data_table.find_all('tr')[1:]  # Skip header row
    else:
        notifications = tbody.find_all('tr')
    
    logger.info(f"Found {len(notifications)} notification rows on website")
    
    current_data = {}
    
    for row_idx, row in enumerate(notifications):
        cols = row.find_all(['td', 'th'])
        
        if len(cols) < 5:
            continue
            
        try:
            # Extract data from the 5 columns
            date_reported_str = cols[0].get_text(strip=True)
            org_name = cols[1].get_text(strip=True)
            date_of_breach_str = cols[2].get_text(strip=True)
            residents_affected_str = cols[3].get_text(strip=True)
            information_compromised_str = cols[4].get_text(strip=True)
            
            # Extract PDF URL
            pdf_url = extract_pdf_url_wa(cols[1])
            
            # Parse structured data
            affected_individuals = parse_affected_individuals_wa(residents_affected_str)
            breach_date_only = parse_date_to_date_only(date_of_breach_str)
            reported_date_only = parse_date_to_date_only(date_reported_str)
            data_types_compromised = parse_data_types_compromised_wa(information_compromised_str)
            
            # Store the parsed data
            current_data[org_name] = {
                'affected_individuals': affected_individuals,
                'breach_date': breach_date_only,
                'reported_date': reported_date_only,
                'notice_document_url': pdf_url,
                'data_types_compromised': data_types_compromised,
                'raw_data': {
                    'date_reported_raw': date_reported_str,
                    'date_of_breach_raw': date_of_breach_str,
                    'wa_residents_affected_raw': residents_affected_str,
                    'information_compromised_raw': information_compromised_str,
                    'pdf_url': pdf_url
                }
            }
            
        except Exception as e:
            logger.warning(f"Error processing row {row_idx+1}: {e}")
            continue
    
    logger.info(f"Successfully parsed {len(current_data)} breach records from website")
    return current_data

def fix_washington_ag_data_quality():
    """
    Fix data quality issues in existing Washington AG records.
    """
    logger.info("Starting Washington AG data quality fix...")
    
    # Get current website data
    current_website_data = scrape_current_washington_data()
    if not current_website_data:
        logger.error("Failed to scrape current website data")
        return False
    
    # Initialize Supabase client
    supabase_client = SupabaseClient()
    
    # Get all Washington AG records that need fixing
    logger.info("Fetching Washington AG records from database...")
    
    try:
        response = supabase_client.client.table("scraped_items").select(
            "id, title, affected_individuals, breach_date, reported_date, notice_document_url, raw_data_json"
        ).eq("source_id", 5).order("id", desc=True).execute()
        
        records = response.data if response.data else []
        logger.info(f"Found {len(records)} Washington AG records in database")
        
        fixed_count = 0
        for i, record in enumerate(records):
            record_id = record['id']
            title = record['title']
            
            logger.info(f"Processing record {i+1}/{len(records)}: {title} (ID: {record_id})")
            
            # Find matching data from current website
            website_data = current_website_data.get(title)
            if not website_data:
                logger.info(f"No matching data found on website for: {title}")
                continue
            
            # Prepare update data
            update_data = {}
            
            # Fix affected_individuals if missing or different
            if not record['affected_individuals'] and website_data['affected_individuals']:
                update_data['affected_individuals'] = website_data['affected_individuals']
                logger.info(f"  Found affected_individuals: {website_data['affected_individuals']}")
            
            # Fix breach_date if missing
            if not record['breach_date'] and website_data['breach_date']:
                update_data['breach_date'] = website_data['breach_date']
                logger.info(f"  Found breach_date: {website_data['breach_date']}")
            
            # Fix reported_date if missing
            if not record['reported_date'] and website_data['reported_date']:
                update_data['reported_date'] = website_data['reported_date']
                logger.info(f"  Found reported_date: {website_data['reported_date']}")
            
            # Fix notice_document_url if missing
            if not record['notice_document_url'] and website_data['notice_document_url']:
                update_data['notice_document_url'] = website_data['notice_document_url']
                logger.info(f"  Found notice_document_url: {website_data['notice_document_url']}")
            
            # Update raw_data_json with current website data
            if website_data['raw_data']:
                current_raw_data = record.get('raw_data_json', {})
                current_raw_data['washington_ag_raw_updated'] = website_data['raw_data']
                current_raw_data['data_quality_fix_timestamp'] = datetime.now().isoformat()
                update_data['raw_data_json'] = current_raw_data
                logger.info(f"  Updated raw_data_json with current website data")
            
            # Update the record if we found any fixes
            if update_data:
                try:
                    update_response = supabase_client.client.table("scraped_items").update(update_data).eq("id", record_id).execute()
                    if update_response.data:
                        fixed_count += 1
                        logger.info(f"Updated record {record_id} with {list(update_data.keys())}")
                    else:
                        logger.warning(f"Failed to update record {record_id}")
                except Exception as e:
                    logger.error(f"Error updating record {record_id}: {e}")
            else:
                logger.info(f"No fixes needed for record {record_id}")
        
        logger.info(f"Data quality fix completed. Fixed {fixed_count} out of {len(records)} records.")
        
    except Exception as e:
        logger.error(f"Error during data quality fix: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = fix_washington_ag_data_quality()
    if success:
        logger.info("Washington AG data quality fix completed successfully!")
    else:
        logger.error("Washington AG data quality fix failed!")
        sys.exit(1)
