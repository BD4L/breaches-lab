import os
from supabase import create_client, Client
import logging
import re

logger = logging.getLogger(__name__)

def clean_text_for_database(text):
    """
    Clean text content to make it safe for PostgreSQL storage.
    Removes null bytes and other problematic characters that cause database errors.

    Args:
        text: String to clean, or None

    Returns:
        Cleaned string safe for database storage, or None if input was None
    """
    if text is None:
        return None

    if not isinstance(text, str):
        # Convert to string if it's not already
        text = str(text)

    # Remove null bytes (the main cause of the Unicode error)
    text = text.replace('\u0000', '')

    # Remove other problematic control characters but preserve newlines and tabs
    # This removes characters in the range 0x00-0x08, 0x0B-0x0C, 0x0E-0x1F
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]', '', text)

    # Remove any remaining null-like characters that might cause issues
    text = text.replace('\x00', '')

    return text

def clean_data_recursively(data):
    """
    Recursively clean text data in dictionaries, lists, and strings.
    This ensures all text content is safe for database storage.

    Args:
        data: Data structure to clean (dict, list, str, or other)

    Returns:
        Cleaned data structure
    """
    if isinstance(data, dict):
        return {key: clean_data_recursively(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [clean_data_recursively(item) for item in data]
    elif isinstance(data, str):
        return clean_text_for_database(data)
    else:
        return data

class SupabaseClient:
    def __init__(self):
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise ValueError("Supabase URL and Key must be set as environment variables.")
        self.client: Client = create_client(url, key)
        logger.info("Supabase client initialized.")

    def check_item_exists(self, item_url: str) -> bool:
        """
        Check if an item with the given URL already exists in the database.
        """
        try:
            response = self.client.table("scraped_items").select("id").eq("item_url", item_url).execute()
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Error checking if item exists for URL {item_url}: {e}")
            return False

    def get_enhancement_status_for_source(self, source_id: int, page_size: int = 1000) -> dict:
        """
        Fetch the enhancement status of every stored item for one source in a single pass,
        keyed by item_url.

        This is the batch equivalent of calling get_item_enhancement_status() once per record.
        Scrapers use it to decide, before doing any network enrichment, whether a record is
        already stored and complete. Doing that per-record cost one round trip per breach and,
        worse, meant the expensive detail-page and PDF work happened before the check.

        Returns {} on failure rather than raising, so a caller that cannot reach the database
        degrades to treating every record as new instead of aborting the run.
        """
        items = {}
        offset = 0
        try:
            while True:
                response = (
                    self.client.table("scraped_items")
                    .select("id, item_url, raw_data_json, affected_individuals, notice_document_url")
                    .eq("source_id", source_id)
                    .order("id")
                    .range(offset, offset + page_size - 1)
                    .execute()
                )
                rows = response.data or []
                for item in rows:
                    items[item["item_url"]] = self._build_enhancement_status(item)
                if len(rows) < page_size:
                    break
                offset += page_size
            logger.info(f"Loaded enhancement status for {len(items)} existing items (source_id={source_id})")
            return items
        except Exception as e:
            logger.error(f"Error batch-loading enhancement status for source {source_id}: {e}")
            return {}

    def _build_enhancement_status(self, item: dict) -> dict:
        """Derive the enhancement-status view of a stored row. Shared by the single and batch paths."""
        raw_data = item.get('raw_data_json', {}) or {}

        status = {
            'exists': True,
            'item_id': item['id'],
            'has_enhancement_errors': False,
            'has_successful_enhancement': False,
            'has_pdf_analysis': False,
            'affected_individuals': item.get('affected_individuals'),
            'notice_document_url': item.get('notice_document_url'),
            'raw_data_json': raw_data,
            'enhancement_errors': []
        }

        tier_2_data = raw_data.get('tier_2_enhanced', {}) if isinstance(raw_data, dict) else {}
        if isinstance(tier_2_data, dict):
            enhancement_errors = tier_2_data.get('enhancement_errors', [])
            if enhancement_errors:
                status['has_enhancement_errors'] = True
                status['enhancement_errors'] = enhancement_errors
            if tier_2_data.get('enhancement_attempted') and not enhancement_errors:
                status['has_successful_enhancement'] = True

        pdf_analysis = raw_data.get('tier_3_pdf_analysis', []) if isinstance(raw_data, dict) else []
        if isinstance(pdf_analysis, list) and pdf_analysis:
            status['has_pdf_analysis'] = any(
                pdf.get('pdf_analyzed', False) for pdf in pdf_analysis if isinstance(pdf, dict)
            )

        return status

    def get_item_enhancement_status(self, item_url: str) -> dict:
        """
        Get the enhancement status of an existing item to determine if it needs updating.
        Returns information about enhancement attempts and success/failure status.
        """
        try:
            response = self.client.table("scraped_items").select(
                "id, raw_data_json, affected_individuals, notice_document_url"
            ).eq("item_url", item_url).execute()

            if not response.data:
                return {'exists': False}

            item = response.data[0]
            raw_data = item.get('raw_data_json', {})

            # Check enhancement status
            enhancement_status = {
                'exists': True,
                'item_id': item['id'],
                'has_enhancement_errors': False,
                'has_successful_enhancement': False,
                'has_pdf_analysis': False,
                'affected_individuals': item.get('affected_individuals'),
                'notice_document_url': item.get('notice_document_url'),
                'raw_data_json': raw_data,  # Include raw data for detailed checking
                'enhancement_errors': []
            }

            # Check for enhancement errors in tier_2_enhanced
            tier_2_data = raw_data.get('tier_2_enhanced', {})
            if isinstance(tier_2_data, dict):
                enhancement_errors = tier_2_data.get('enhancement_errors', [])
                if enhancement_errors:
                    enhancement_status['has_enhancement_errors'] = True
                    enhancement_status['enhancement_errors'] = enhancement_errors

                # Check if enhancement was attempted but failed
                enhancement_attempted = tier_2_data.get('enhancement_attempted', False)
                detail_page_data = tier_2_data.get('detail_page_data', {})

                if enhancement_attempted and detail_page_data:
                    if detail_page_data.get('detail_page_scraped', False):
                        enhancement_status['has_successful_enhancement'] = True

            # Check for PDF analysis
            tier_3_data = raw_data.get('tier_3_pdf_analysis', [])
            if tier_3_data:
                # Check if any PDF was successfully analyzed
                for pdf_analysis in tier_3_data:
                    if isinstance(pdf_analysis, dict) and pdf_analysis.get('pdf_analyzed', False):
                        enhancement_status['has_pdf_analysis'] = True
                        break

            return enhancement_status

        except Exception as e:
            logger.error(f"Error getting item enhancement status: {e}")
            return {'exists': False}

    def update_item_enhancement(self, item_id: str, enhanced_data: dict) -> bool:
        """
        Update an existing item with new enhancement data.
        Used when we have better enhancement data than what was previously stored.
        """
        try:
            # Prepare update data
            update_data = {}

            # Update affected individuals if we have new data
            if enhanced_data.get('affected_individuals') is not None:
                update_data['affected_individuals'] = enhanced_data['affected_individuals']

            # Update notice document URL if we have new data
            if enhanced_data.get('notice_document_url'):
                update_data['notice_document_url'] = clean_text_for_database(enhanced_data['notice_document_url'])

            # Update what_was_leaked if we have new data
            if enhanced_data.get('what_was_leaked'):
                update_data['what_was_leaked'] = clean_text_for_database(enhanced_data['what_was_leaked'])

            # Update summary and content if we have enhanced versions
            if enhanced_data.get('summary_text'):
                update_data['summary_text'] = clean_text_for_database(enhanced_data['summary_text'])

            if enhanced_data.get('full_content'):
                update_data['full_content'] = clean_text_for_database(enhanced_data['full_content'])

            # Update raw_data_json with new enhancement data (clean recursively)
            if enhanced_data.get('raw_data_json'):
                update_data['raw_data_json'] = clean_data_recursively(enhanced_data['raw_data_json'])

            # Perform the update
            response = self.client.table("scraped_items").update(update_data).eq("id", item_id).execute()

            if response.data:
                logger.info(f"Successfully updated item enhancement data for ID: {item_id}")
                return True
            else:
                logger.error(f"Failed to update item enhancement data for ID: {item_id}")
                return False

        except Exception as e:
            logger.error(f"Error updating item enhancement: {e}")
            return False

    def insert_item(self, source_id: int, item_url: str, title: str, publication_date: str, summary_text: str = None, full_content: str = None, raw_data_json: dict = None, tags_keywords: list = None, affected_individuals: int = None, breach_date: str = None, reported_date: str = None, notice_document_url: str = None, what_was_leaked: str = None,
                    # SEC-specific fields
                    cik: str = None, ticker_symbol: str = None, accession_number: str = None, form_type: str = None, filing_date: str = None, report_date: str = None, primary_document_url: str = None, xbrl_instance_url: str = None,
                    items_disclosed: list = None, is_cybersecurity_related: bool = None, is_amendment: bool = None, is_delayed_disclosure: bool = None,
                    incident_nature_text: str = None, incident_scope_text: str = None, incident_timing_text: str = None, incident_impact_text: str = None, incident_unknown_details_text: str = None,
                    incident_discovery_date: str = None, incident_disclosure_date: str = None, incident_containment_date: str = None,
                    estimated_cost_min: float = None, estimated_cost_max: float = None, estimated_cost_currency: str = None, data_types_compromised: list = None,
                    exhibit_urls: list = None, keywords_detected: list = None, keyword_contexts: dict = None, file_size_bytes: int = None,
                    business_description: str = None, industry_classification: str = None):
        """
        Inserts a single item into the scraped_items table.
        publication_date should be an ISO 8601 string.
        """
        try:
            data_to_insert = {
                # Core fields
                "source_id": source_id,
                "item_url": item_url,
                "title": title,
                "publication_date": publication_date,
                "summary_text": summary_text,
                "full_content": full_content,
                "raw_data_json": raw_data_json,
                "tags_keywords": tags_keywords,

                # Standardized breach fields
                "affected_individuals": affected_individuals,
                "breach_date": breach_date,
                "reported_date": reported_date,
                "notice_document_url": notice_document_url,
                "what_was_leaked": what_was_leaked,

                # SEC-specific fields
                "cik": cik,
                "ticker_symbol": ticker_symbol,
                "accession_number": accession_number,
                "form_type": form_type,
                "filing_date": filing_date,
                "report_date": report_date,
                "primary_document_url": primary_document_url,
                "xbrl_instance_url": xbrl_instance_url,
                "items_disclosed": items_disclosed,
                "is_cybersecurity_related": is_cybersecurity_related,
                "is_amendment": is_amendment,
                "is_delayed_disclosure": is_delayed_disclosure,
                "incident_nature_text": incident_nature_text,
                "incident_scope_text": incident_scope_text,
                "incident_timing_text": incident_timing_text,
                "incident_impact_text": incident_impact_text,
                "incident_unknown_details_text": incident_unknown_details_text,
                "incident_discovery_date": incident_discovery_date,
                "incident_disclosure_date": incident_disclosure_date,
                "incident_containment_date": incident_containment_date,
                "estimated_cost_min": estimated_cost_min,
                "estimated_cost_max": estimated_cost_max,
                "estimated_cost_currency": estimated_cost_currency,
                "data_types_compromised": data_types_compromised,
                "exhibit_urls": exhibit_urls,
                "keywords_detected": keywords_detected,
                "keyword_contexts": keyword_contexts,
                "file_size_bytes": file_size_bytes,
                "business_description": business_description,
                "industry_classification": industry_classification,
                # scraped_at and created_at have defaults in the DB
            }
            # Remove keys where value is None to rely on DB defaults or avoid inserting nulls unnecessarily for optional fields
            data_to_insert = {k: v for k, v in data_to_insert.items() if v is not None}

            # Clean all text data to prevent Unicode errors in PostgreSQL
            data_to_insert = clean_data_recursively(data_to_insert)

            response = self.client.table("scraped_items").insert(data_to_insert).execute()

            # Check for errors in the response
            if hasattr(response, 'error') and response.error:
                logger.error(f"Supabase error inserting item {item_url}: {response.error}")
                return None

            if response.data:
                logger.info(f"Successfully inserted item: {item_url}")
                return response.data[0]
            else:
                logger.warning(f"No data returned for item {item_url}, but no error reported")
                return None

        except Exception as e:
            # Enhanced error logging with more details
            logger.error(f"Error inserting item {item_url}: {e}")
            logger.error(f"Data being inserted: {data_to_insert}")
            if hasattr(e, 'details'):
                logger.error(f"Error details: {e.details}")
            if hasattr(e, 'message'):
                logger.error(f"Error message: {e.message}")
            if hasattr(e, 'code'):
                logger.error(f"Error code: {e.code}")
            return None

    # We can add more methods later, e.g., for inserting into 'data_sources'
    # or for querying/updating records.

def get_supabase_client():
    """
    Get a Supabase client instance for use in email alerts and other utilities.
    Returns the raw Supabase client, not the SupabaseClient wrapper.
    """
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise ValueError("Supabase URL and Key must be set as environment variables.")
    return create_client(url, key)
