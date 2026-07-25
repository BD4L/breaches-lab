#!/usr/bin/env python3
"""
Data Quality Fix Script for California AG Records

This script fixes data quality issues in existing California AG breach records:
1. Converts breach_date from string to proper DATE format
2. Extracts affected_individuals from raw_data_json
3. Populates missing fields from available data

Run this script to fix existing records after the Unicode and data quality improvements.
"""

import os
import sys
import logging
from datetime import datetime

# Add the parent directory to the path so we can import from utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.supabase_client import SupabaseClient

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_date_flexible(date_str):
    """
    Parse date string in various formats to YYYY-MM-DD format.
    """
    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip()
    if not date_str:
        return None

    # Common date formats
    date_formats = [
        '%m/%d/%Y',    # 02/03/2025
        '%Y-%m-%d',    # 2025-02-03
        '%m-%d-%Y',    # 02-03-2025
        '%Y/%m/%d',    # 2025/02/03
        '%d/%m/%Y',    # 03/02/2025 (less common)
    ]

    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            return parsed_date.strftime('%Y-%m-%d')
        except ValueError:
            continue

    logger.warning(f"Could not parse date: {date_str}")
    return None

def extract_affected_individuals_from_raw_data(raw_data_json):
    """
    Extract affected individuals count from raw_data_json structure.
    """
    if not raw_data_json or not isinstance(raw_data_json, dict):
        return None

    # Check pdf_analysis_summary first (most reliable)
    pdf_summary = raw_data_json.get('pdf_analysis_summary', {})
    if isinstance(pdf_summary, dict):
        affected_extracted = pdf_summary.get('affected_individuals_extracted')
        if affected_extracted and isinstance(affected_extracted, (int, str)):
            try:
                count = int(str(affected_extracted).replace(',', ''))
                if 10 <= count <= 100000000:  # Reasonable range
                    return count
            except (ValueError, TypeError):
                pass

    # Check tier_3_pdf_analysis data
    tier_3_pdf = raw_data_json.get('tier_3_pdf_analysis', [])
    if isinstance(tier_3_pdf, list):
        for pdf_analysis in tier_3_pdf:
            if isinstance(pdf_analysis, dict):
                affected_data = pdf_analysis.get('affected_individuals', {})
                if isinstance(affected_data, dict) and affected_data.get('count'):
                    try:
                        count = int(affected_data['count'])
                        if 10 <= count <= 100000000:  # Reasonable range
                            return count
                    except (ValueError, TypeError):
                        continue

    # Check tier_1_csv_data (actual structure used)
    tier_1_csv_data = raw_data_json.get('tier_1_csv_data', {})
    if isinstance(tier_1_csv_data, dict):
        # Look for affected individuals in various fields
        for field in ['affected_individuals', 'individuals_affected', 'number_affected', 'Number of Individuals']:
            if field in tier_1_csv_data and tier_1_csv_data[field]:
                try:
                    count = int(str(tier_1_csv_data[field]).replace(',', ''))
                    if 10 <= count <= 100000000:  # Reasonable range
                        return count
                except (ValueError, TypeError):
                    continue

    # Fallback: Check tier_1_csv data (older structure)
    tier_1_csv = raw_data_json.get('tier_1_csv', {})
    if isinstance(tier_1_csv, dict):
        # Look for affected individuals in various fields
        for field in ['affected_individuals', 'individuals_affected', 'number_affected']:
            if field in tier_1_csv and tier_1_csv[field]:
                try:
                    count = int(str(tier_1_csv[field]).replace(',', ''))
                    if 10 <= count <= 100000000:  # Reasonable range
                        return count
                except (ValueError, TypeError):
                    continue

    return None

def extract_breach_date_from_raw_data(raw_data_json):
    """
    Extract breach date from raw_data_json structure.
    """
    if not raw_data_json or not isinstance(raw_data_json, dict):
        return None

    # Check tier_1_csv_data (the actual structure used)
    tier_1_csv_data = raw_data_json.get('tier_1_csv_data', {})
    if isinstance(tier_1_csv_data, dict):
        # Look for breach date in the actual field name
        breach_date_field = tier_1_csv_data.get('Date(s) of Breach  (if known)', '')
        if breach_date_field and breach_date_field.strip():
            return parse_date_flexible(breach_date_field.strip())

    # Fallback: Check tier_1_csv data (older structure)
    tier_1_csv = raw_data_json.get('tier_1_csv', {})
    if isinstance(tier_1_csv, dict):
        # Look for breach date in various fields
        for field in ['breach_date', 'incident_date', 'date_of_breach', 'Date(s) of Breach  (if known)']:
            if field in tier_1_csv and tier_1_csv[field]:
                return parse_date_flexible(tier_1_csv[field])

    return None

def fix_california_ag_data_quality():
    """
    Fix data quality issues in existing California AG records.
    """
    logger.info("Starting California AG data quality fix...")

    # Initialize Supabase client
    supabase_client = SupabaseClient()

    # Get all California AG records that need fixing
    logger.info("Fetching California AG records that need data quality fixes...")

    try:
        # Query for records missing breach_date or affected_individuals
        response = supabase_client.client.table("scraped_items").select(
            "id, title, breach_date, affected_individuals, raw_data_json, reported_date"
        ).eq("source_id", 4).is_("breach_date", "null").order("id", desc=True).limit(50).execute()

        records = response.data if response.data else []

        logger.info(f"Found {len(records)} California AG records that need data quality fixes")

        fixed_count = 0
        for i, record in enumerate(records):
            record_id = record['id']
            title = record['title']
            raw_data_json = record['raw_data_json']

            logger.info(f"Processing record {i+1}/{len(records)}: {title} (ID: {record_id})")

            # Prepare update data
            update_data = {}

            # Fix breach_date if missing
            if not record['breach_date']:
                breach_date = extract_breach_date_from_raw_data(raw_data_json)
                if breach_date:
                    update_data['breach_date'] = breach_date
                    logger.info(f"  Found breach_date: {breach_date}")

            # Fix affected_individuals if missing
            if not record['affected_individuals']:
                affected_count = extract_affected_individuals_from_raw_data(raw_data_json)
                if affected_count:
                    update_data['affected_individuals'] = affected_count
                    logger.info(f"  Found affected_individuals: {affected_count}")

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
    success = fix_california_ag_data_quality()
    if success:
        logger.info("California AG data quality fix completed successfully!")
    else:
        logger.error("California AG data quality fix failed!")
        sys.exit(1)
