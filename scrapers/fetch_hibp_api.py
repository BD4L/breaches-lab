import os
import logging
import requests
import time
from datetime import datetime
from urllib.parse import urljoin, quote # quote for URL encoding breach name
from dateutil import parser as dateutil_parser

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
HIBP_API_BASE_URL = "https://haveibeenpwned.com/api/v3"
HIBP_BREACHES_ENDPOINT = "/breaches"
SOURCE_ID_HIBP = 36
USER_AGENT = "PwnedBreachScraper/1.0 (github.com/ComprehensiveBreachDataDashboard/Breaches)" # Example User-Agent

# HIBP API recommends a delay of 1500ms (1.5s) between calls to a single API endpoint.
# The /breaches endpoint is a single call, but good practice if we add more later.
HIBP_API_DELAY_SECONDS = 2.0

def parse_date_hibp(date_str: str) -> str | None:
    """
    Parses date string (YYYY-MM-DD or YYYY-MM-DDTHH:mm:ssZ) to ISO 8601 (YYYY-MM-DDTHH:MM:SS).
    """
    if not date_str:
        return None
    try:
        # dateutil.parser is good at handling various ISO-like formats including ones with 'Z'
        dt_object = dateutil_parser.isoparse(date_str) 
        return dt_object.isoformat()
    except (ValueError, TypeError) as e:
        # Fallback for simple YYYY-MM-DD if isoparse fails (though isoparse should handle it)
        try:
            dt_object = datetime.strptime(date_str, "%Y-%m-%d")
            return dt_object.isoformat()
        except (ValueError, TypeError) as e_fallback:
            logger.warning(f"Could not parse date string from HIBP: '{date_str}'. Error: {e}, Fallback Error: {e_fallback}")
            return None


def process_hibp_breaches():
    """
    Fetches data breaches from the HIBP API and inserts them into Supabase.
    """
    logger.info("Starting Have I Been Pwned (HIBP) API processing...")

    hibp_api_key = os.environ.get("HIBP_API_KEY")
    if not hibp_api_key:
        logger.error("CRITICAL: HIBP_API_KEY environment variable not found. This script cannot run without an API key.")
        logger.error("Please set the HIBP_API_KEY environment variable with your key from https://haveibeenpwned.com/API/Key")
        return

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    headers = {
        'hibp-api-key': hibp_api_key,
        'User-Agent': USER_AGENT,
        'Accept': 'application/json' # Expecting JSON response
    }

    api_url = HIBP_API_BASE_URL + HIBP_BREACHES_ENDPOINT
    
    logger.info(f"Requesting all breaches from HIBP API: {api_url}")
    # Implement delay before API call as per HIBP guidelines
    logger.info(f"Waiting for {HIBP_API_DELAY_SECONDS} seconds before making API call due to rate limits...")
    time.sleep(HIBP_API_DELAY_SECONDS)

    try:
        response = requests.get(api_url, headers=headers, timeout=60) # Increased timeout for potentially large response
        
        if response.status_code == 401: # Unauthorized
            logger.error(f"HIBP API request failed with status 401 (Unauthorized). Check your HIBP_API_KEY. Response: {response.text}")
            return
        elif response.status_code == 403: # Forbidden
             logger.error(f"HIBP API request failed with status 403 (Forbidden). User agent not approved or other policy issue. Response: {response.text}")
             return
        elif response.status_code == 429: # Too Many Requests
            logger.error(f"HIBP API request failed with status 429 (Too Many Requests). Rate limit exceeded. Retry later. Check 'retry-after' header if present: {response.headers.get('retry-after')}")
            return
            
        response.raise_for_status() # Raise an exception for other bad status codes (4xx or 5xx)
        
        breaches_data = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data from HIBP API ({api_url}): {e}", exc_info=True)
        return
    except ValueError as e_json: # Includes JSONDecodeError
        logger.error(f"Error decoding JSON response from HIBP API ({api_url}): {e_json}. Response text: {response.text[:500]}")
        return

    if not breaches_data:
        logger.info("No breach data returned from HIBP API.")
        return

    logger.info(f"Successfully fetched {len(breaches_data)} breach entries from HIBP API.")

    inserted_count = 0
    processed_count = 0
    skipped_count = 0

    # Load the URLs already stored for this source once, so the loop can skip known breaches
    # without a query each. HIBP returns its entire catalogue on every call and almost all of it
    # is already stored, so this turns ~800 rejected inserts per run into one read.
    existing_item_urls = set()
    try:
        offset, page_size = 0, 1000
        while True:
            page = (supabase_client.client.table("scraped_items")
                    .select("item_url")
                    .eq("source_id", SOURCE_ID_HIBP)
                    .order("id")
                    .range(offset, offset + page_size - 1)
                    .execute())
            rows = page.data or []
            existing_item_urls.update(r["item_url"] for r in rows if r.get("item_url"))
            if len(rows) < page_size:
                break
            offset += page_size
        logger.info(f"Loaded {len(existing_item_urls)} existing HIBP item URLs for deduplication")
    except Exception as e:
        # Degrade to the previous behaviour rather than aborting: the UNIQUE constraint still
        # prevents duplicates, it is just noisier and slower.
        logger.warning(f"Could not preload existing HIBP items ({e}); relying on insert conflicts")

    for breach_entry in breaches_data:
        processed_count += 1
        try:
            name = breach_entry.get("Name")
            title = breach_entry.get("Title", name) # Use Name if Title is missing
            domain = breach_entry.get("Domain")
            breach_date_str = breach_entry.get("BreachDate") # Format: "YYYY-MM-DD"
            added_date_str = breach_entry.get("AddedDate") # Format: "YYYY-MM-DDTHH:mm:ssZ"
            modified_date_str = breach_entry.get("ModifiedDate") # Format: "YYYY-MM-DDTHH:mm:ssZ"
            pwn_count = breach_entry.get("PwnCount")
            description = breach_entry.get("Description")
            data_classes = breach_entry.get("DataClasses", []) # Array of strings
            
            is_verified = breach_entry.get("IsVerified", False)
            is_fabricated = breach_entry.get("IsFabricated", False)
            is_sensitive = breach_entry.get("IsSensitive", False)
            is_retired = breach_entry.get("IsRetired", False)
            is_spam_list = breach_entry.get("IsSpamList", False)
            logo_path = breach_entry.get("LogoPath") # URL to a logo image

            if not name:
                logger.warning(f"Skipping HIBP entry due to missing 'Name'. Entry: {breach_entry}")
                skipped_count += 1
                continue

            # Construct item_url: https://haveibeenpwned.com/PwnedWebsites#[BreachName]
            # The [BreachName] part needs to be URL-encoded if it contains special characters.
            # However, HIBP uses the 'Name' directly as the anchor.
            item_url = f"https://haveibeenpwned.com/PwnedWebsites#{quote(name)}"

            publication_date_iso = parse_date_hibp(breach_date_str)
            if not publication_date_iso:
                logger.warning(f"Skipping HIBP entry '{name}' due to unparsable BreachDate: '{breach_date_str}'. Using AddedDate as fallback.")
                publication_date_iso = parse_date_hibp(added_date_str) # Fallback to AddedDate
                if not publication_date_iso:
                    logger.error(f"Critical: Could not parse BreachDate or AddedDate for HIBP entry '{name}'. Skipping.")
                    skipped_count +=1
                    continue


            raw_data = {
                "hibp_name": name, # Store the original HIBP Name as it's an ID
                "domain": domain,
                "added_date_hibp": parse_date_hibp(added_date_str),
                "modified_date_hibp": parse_date_hibp(modified_date_str),
                "pwn_count": pwn_count,
                "data_classes_hibp": data_classes,
                "is_verified_hibp": is_verified,
                "is_fabricated_hibp": is_fabricated,
                "is_sensitive_hibp": is_sensitive,
                "is_retired_hibp": is_retired,
                "is_spam_list_hibp": is_spam_list,
                "logo_path_hibp": logo_path
            }
            # Clean None values from raw_data
            raw_data_json = {k: v for k, v in raw_data.items() if v is not None}


            tags = ["hibp", "data_breach"]
            if data_classes:
                # Sanitize data classes for use as tags (lowercase, replace space with underscore)
                sanitized_data_classes = [dc.lower().replace(" ", "_").replace("'", "") for dc in data_classes]
                tags.extend(sanitized_data_classes)
            if is_verified: tags.append("verified_breach")
            if is_sensitive: tags.append("sensitive_breach")
            if is_fabricated: tags.append("fabricated_breach") # Unlikely to be useful but good to know
            if is_retired: tags.append("retired_breach") # Data no longer searchable on HIBP
            if is_spam_list: tags.append("spam_list")
            
            tags = list(set(tags)) # Ensure unique tags


            item_data = {
                "source_id": SOURCE_ID_HIBP,
                "item_url": item_url,
                "title": title,
                "publication_date": publication_date_iso,
                "summary_text": description,
                "raw_data_json": raw_data_json,
                "tags_keywords": tags
            }
            
            # Skip anything already stored. Without this the whole HIBP catalogue was re-sent on
            # every run and the only thing preventing duplicates was the UNIQUE constraint
            # rejecting each insert, which produced an error log line per breach and paid for a
            # round trip per breach. existing_item_urls is loaded once before the loop.
            if item_url in existing_item_urls:
                skipped_count += 1
                continue

            insert_response = supabase_client.insert_item(**item_data)
            if insert_response:
                # logger.debug(f"Successfully inserted HIBP item for '{name}'.")
                inserted_count += 1
            else:
                logger.error(f"Failed to insert HIBP item for '{name}'.")

        except Exception as e:
            logger.error(f"Error processing HIBP entry '{breach_entry.get('Name', 'Unknown Name')}': {e}", exc_info=True)
            skipped_count +=1

    logger.info(f"Finished processing HIBP breaches. Total entries: {processed_count}. Inserted: {inserted_count}. Skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("Have I Been Pwned (HIBP) API Scraper Started")
    
    # Remind user about API key if running directly and it's not set.
    # The main function already checks and logs this, but an initial reminder can be helpful.
    if not os.environ.get("HIBP_API_KEY"):
        print("-----------------------------------------------------------------------------------")
        print("WARNING: HIBP_API_KEY environment variable is not set.")
        print("This script requires an API key from Have I Been Pwned to function.")
        print("Please visit https://haveibeenpwned.com/API/Key to obtain a key and set it as an environment variable.")
        print("-----------------------------------------------------------------------------------")

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set for Supabase client.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_hibp_breaches()
        
    logger.info("Have I Been Pwned (HIBP) API Scraper Finished")
