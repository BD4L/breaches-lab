import os
import logging
import requests # feedparser might use it, good to have for potential fallbacks or direct fetches if needed
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dateutil import parser as dateutil_parser
import time # For converting time_struct to datetime
import concurrent.futures
from typing import Dict, Tuple

import yaml

# Handle imports for both direct execution and module import
try:
    from .breach_intelligence import process_breach_intelligence
except ImportError:
    # Direct execution - add parent directory to path
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from scrapers.breach_intelligence import process_breach_intelligence

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

# Path to the configuration file
CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')

# Headers for feedparser/requests. Some feeds might require a User-Agent.
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/rss+xml, application/xml, text/xml, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive'
}

# Configuration
FILTER_DAYS_BACK = int(os.environ.get("NEWS_FILTER_DAYS_BACK", "19"))  # Process news from last N days (from June 1st, 2025)
MAX_ITEMS_PER_FEED = int(os.environ.get("NEWS_MAX_ITEMS_PER_FEED", "25"))  # Limit items per feed (reduced for performance with 18 feeds)
PROCESSING_MODE = os.environ.get("NEWS_PROCESSING_MODE", "ENHANCED")  # BASIC, ENHANCED
BREACH_INTELLIGENCE_ENABLED = os.environ.get("BREACH_INTELLIGENCE_ENABLED", "true").lower() == "true"
BREACH_CONFIDENCE_THRESHOLD = float(os.environ.get("BREACH_CONFIDENCE_THRESHOLD", "0.3"))  # Minimum confidence for breach detection
CONCURRENT_FEEDS = int(os.environ.get("NEWS_CONCURRENT_FEEDS", "3"))  # Number of feeds to process concurrently
FEED_TIMEOUT = int(os.environ.get("NEWS_FEED_TIMEOUT", "30"))  # Timeout per feed in seconds

def clean_html(html_content: str, max_length: int = 500) -> str:
    """Strips HTML from a string and truncates it."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    return (text[:max_length] + '...') if len(text) > max_length else text

def parse_feed_date(entry) -> str | None:
    """
    Parses date from a feed entry, trying various common fields.
    Returns ISO 8601 string or None.
    """
    date_to_parse = None
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        date_to_parse = entry.published_parsed
    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        date_to_parse = entry.updated_parsed
    elif hasattr(entry, 'created_parsed') and entry.created_parsed: # Less common
        date_to_parse = entry.created_parsed
    elif hasattr(entry, 'published') and entry.published: # Fallback to string parsing
        try: return dateutil_parser.parse(entry.published).isoformat()
        except (ValueError, TypeError): pass
    elif hasattr(entry, 'updated') and entry.updated:
        try: return dateutil_parser.parse(entry.updated).isoformat()
        except (ValueError, TypeError): pass
    
    if date_to_parse:
        try:
            # feedparser's *_parsed fields return a time.struct_time
            return datetime.fromtimestamp(time.mktime(date_to_parse)).isoformat()
        except (TypeError, ValueError) as e:
            logger.warning(f"Could not parse time.struct_time {date_to_parse}: {e}")
            return None
    return None

def fetch_feed_with_fallback(feed_url: str, feed_name: str) -> feedparser.FeedParserDict:
    """
    Fetch RSS feed with enhanced fallback handling for various feed types.
    Returns parsed feed or empty feed on failure.
    """
    try:
        # Special handling for different feed types
        custom_headers = REQUEST_HEADERS.copy()

        # Reddit feeds need specific user agent
        if 'reddit.com' in feed_url:
            custom_headers['User-Agent'] = 'BreachDashboard/1.0 (by /u/breachdashboard)'

        # CISA feeds sometimes need specific headers
        elif 'cisa.gov' in feed_url:
            custom_headers['Accept'] = 'application/xml, text/xml, */*'

        # First try: Direct feedparser with custom user agent
        parsed_feed = feedparser.parse(feed_url, agent=custom_headers['User-Agent'])

        # Check if we got entries or if there was an SSL error
        if parsed_feed.entries or not parsed_feed.bozo:
            logger.debug(f"Successfully fetched {feed_name} with {len(parsed_feed.entries)} entries")
            return parsed_feed

        # If bozo bit is set and it's an SSL error, try with requests
        if parsed_feed.bozo and 'SSL' in str(parsed_feed.bozo_exception):
            logger.info(f"SSL error for {feed_name}, trying with requests fallback...")

            # Try with requests and custom headers
            response = requests.get(feed_url, headers=custom_headers, timeout=FEED_TIMEOUT, verify=False)
            response.raise_for_status()

            # Parse the content with feedparser
            parsed_feed = feedparser.parse(response.content)
            logger.debug(f"Fallback successful for {feed_name} with {len(parsed_feed.entries)} entries")
            return parsed_feed

    except requests.exceptions.SSLError:
        logger.warning(f"SSL error for {feed_name}, trying without SSL verification...")
        try:
            response = requests.get(feed_url, headers=custom_headers, timeout=FEED_TIMEOUT, verify=False)
            response.raise_for_status()
            parsed_feed = feedparser.parse(response.content)
            logger.debug(f"No-SSL fallback successful for {feed_name}")
            return parsed_feed
        except Exception as e:
            logger.error(f"Failed to fetch {feed_name} even without SSL verification: {e}")
    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching {feed_name} after {FEED_TIMEOUT}s")
    except Exception as e:
        logger.error(f"Error fetching feed {feed_name}: {e}")

    # Return empty feed on failure
    logger.warning(f"Returning empty feed for {feed_name}")
    empty_feed = feedparser.FeedParserDict()
    empty_feed.entries = []
    empty_feed.bozo = False
    return empty_feed

def should_process_news_item(publication_date_iso: str) -> bool:
    """
    Check if news item should be processed based on date filtering.
    """
    if not publication_date_iso or FILTER_DAYS_BACK <= 0:
        return True

    try:
        cutoff_date = datetime.now() - timedelta(days=FILTER_DAYS_BACK)
        item_date = dateutil_parser.parse(publication_date_iso)
        return item_date.replace(tzinfo=None) >= cutoff_date
    except (ValueError, TypeError):
        # If date parsing fails, include the item
        return True

def process_single_feed(feed_info: Dict, supabase_client) -> Tuple[str, int, int, int]:
    """
    Process a single RSS feed and return statistics.
    Returns: (feed_name, processed_count, inserted_count, skipped_count)
    """
    feed_name = feed_info.get("name")
    feed_url = feed_info.get("url")
    source_id = feed_info.get("source_id")

    if not all([feed_name, feed_url, source_id]):
        logger.warning(f"Skipping feed entry due to missing name, url, or source_id in config: {feed_info}")
        return feed_name or "Unknown", 0, 0, 1

    logger.info(f"Processing feed: {feed_name}")

    try:
        # Use enhanced feed fetching with SSL fallback
        parsed_feed = fetch_feed_with_fallback(feed_url, feed_name)

        if parsed_feed.bozo:
            logger.warning(f"Feed {feed_name} may be ill-formed. Bozo bit set. Exception: {parsed_feed.bozo_exception}")

        if not parsed_feed.entries:
            logger.info(f"No entries found in feed {feed_name}")
            if feed_name == "Threatpost":
                logger.info("Threatpost has ceased new publications, so an empty feed is expected.")
            return feed_name, 0, 0, 0

        logger.info(f"Found {len(parsed_feed.entries)} entries in {feed_name}")

        feed_inserted_count = 0
        feed_processed_count = 0
        feed_skipped_count = 0

        # Limit entries per feed for performance
        entries_to_process = parsed_feed.entries[:MAX_ITEMS_PER_FEED] if MAX_ITEMS_PER_FEED > 0 else parsed_feed.entries

        for entry in entries_to_process:
            feed_processed_count += 1
            try:
                title = entry.get("title", "No Title Provided")
                item_url = entry.get("link")

                if not item_url:
                    logger.warning(f"Skipping entry in {feed_name} due to missing item URL. Title: '{title}'")
                    feed_skipped_count += 1
                    continue

                publication_date_iso = parse_feed_date(entry)
                if not publication_date_iso:
                    logger.warning(f"No parsable publication date found for entry '{title}' in {feed_name}. Using current time as fallback.")
                    publication_date_iso = datetime.now().isoformat()

                # Check if item already exists in database (duplicate detection)
                if supabase_client.check_item_exists(item_url):
                    logger.debug(f"Item '{title}' already exists in database. Skipping.")
                    feed_skipped_count += 1
                    continue

                # Apply date filtering
                if not should_process_news_item(publication_date_iso):
                    logger.debug(f"Skipping '{title}' - outside date filter range (older than {FILTER_DAYS_BACK} days)")
                    feed_skipped_count += 1
                    continue

                # Enhanced filtering for breach-focused feeds
                is_breach_focused_feed = any(keyword in feed_name.lower() for keyword in [
                    'breach', 'databreach', 'pwned', 'healthcare', 'bank', 'security'
                ])

                # For breach-focused feeds, apply stricter filtering
                if is_breach_focused_feed:
                    breach_keywords = ['breach', 'hack', 'leak', 'compromise', 'incident', 'attack', 'vulnerability', 'exposed']
                    title_lower = title.lower()
                    summary_lower = (summary_text or "").lower()

                    if not any(keyword in title_lower or keyword in summary_lower for keyword in breach_keywords):
                        logger.debug(f"Skipping '{title}' from {feed_name} - no breach keywords detected")
                        feed_skipped_count += 1
                        continue

                summary_html = entry.get("summary") or entry.get("description")
                summary_text = clean_html(summary_html, max_length=1000)

                # Get full content if available
                full_content = ""
                if entry.get("content"):
                    full_content = clean_html(entry.get("content", [{}])[0].get("value", ""), max_length=5000)

                # Process breach intelligence if enabled
                breach_data = {}
                if BREACH_INTELLIGENCE_ENABLED and PROCESSING_MODE == "ENHANCED":
                    try:
                        breach_intelligence = process_breach_intelligence(
                            title=title,
                            content=full_content or "",
                            summary=summary_text or "",
                            item_url=item_url
                        )

                        # Only include breach data if confidence meets threshold
                        if breach_intelligence.get('is_breach_related') and breach_intelligence.get('confidence_score', 0) >= BREACH_CONFIDENCE_THRESHOLD:
                            breach_data = {
                                'is_cybersecurity_related': True,
                                'affected_individuals': breach_intelligence.get('affected_individuals'),
                                'breach_date': breach_intelligence.get('breach_date'),
                                'what_was_leaked': breach_intelligence.get('what_was_leaked'),
                                'data_types_compromised': breach_intelligence.get('data_types_compromised'),
                                'incident_nature_text': breach_intelligence.get('incident_nature_text'),
                                'keywords_detected': breach_intelligence.get('detected_keywords'),
                                'keyword_contexts': breach_intelligence.get('raw_intelligence', {}).get('keywords_context', {})
                            }
                            logger.info(f"BREACH DETECTED in {feed_name}: {breach_intelligence.get('organization_name','Unknown')} - Confidence: {breach_intelligence.get('confidence_score', 0):.2f}")
                        else:
                            # Still mark as cybersecurity related even if not a breach
                            breach_data['is_cybersecurity_related'] = breach_intelligence.get('is_breach_related', False)

                    except Exception as e:
                        logger.error(f"Error processing breach intelligence for '{title}': {e}")
                        breach_data = {'is_cybersecurity_related': False}

                # Prepare raw_data_json
                raw_data = {
                    "feed_entry_id": entry.get("id"),
                    "authors": [author.get("name") for author in entry.get("authors", []) if author.get("name")],
                    "feed_tags": [tag.get("term") for tag in entry.get("tags", []) if tag.get("term")],
                    "comments_url": entry.get("comments"),
                    "full_content_encoded": entry.get("content", [{}])[0].get("value") if entry.get("content") else None
                }
                # Clean None values from raw_data
                raw_data_json = {k: v for k, v in raw_data.items() if v is not None and v != [] and v != ""}

                tags = [feed_name.lower().replace(" ", "_").replace("/", "_"), "cybersecurity_news"]
                if raw_data_json.get("feed_tags"):
                    # Add sanitized feed tags to our tags list
                    sanitized_feed_tags = [t.lower().replace(" ", "_") for t in raw_data_json["feed_tags"] if len(t) < 50]
                    tags.extend(sanitized_feed_tags)
                tags = list(set(tags))  # Ensure uniqueness

                item_data = {
                    "source_id": source_id,
                    "item_url": item_url,
                    "title": title,
                    "publication_date": publication_date_iso,
                    "summary_text": summary_text,
                    "full_content": full_content if full_content else None,
                    "raw_data_json": raw_data_json if raw_data_json else None,
                    "tags_keywords": tags
                }

                # Merge breach intelligence data if available
                if breach_data:
                    item_data.update(breach_data)

                # Insert item into database
                insert_response = supabase_client.insert_item(**item_data)
                if insert_response:
                    feed_inserted_count += 1
                else:
                    logger.error(f"Failed to insert item '{title}' from {feed_name}. URL: {item_url}")

            except Exception as e:
                logger.error(f"Error processing entry '{entry.get('title', 'Unknown Title')}' from {feed_name}: {e}")
                feed_skipped_count += 1

        logger.info(f"Finished {feed_name}: Processed: {feed_processed_count}, Inserted: {feed_inserted_count}, Skipped: {feed_skipped_count}")
        return feed_name, feed_processed_count, feed_inserted_count, feed_skipped_count

    except Exception as e:
        logger.error(f"Error processing feed {feed_name}: {e}")
        return feed_name, 0, 0, 1

def process_cybersecurity_news_feeds():
    """
    Fetches and processes cybersecurity news from various RSS/Atom feeds,
    and inserts relevant data into Supabase with enhanced error handling and concurrent processing.
    """
    start_time = datetime.now()
    logger.info("Starting Enhanced Cybersecurity News Feed processing...")
    logger.info(f"Configuration: {FILTER_DAYS_BACK} days filter, {MAX_ITEMS_PER_FEED} items/feed, {CONCURRENT_FEEDS} concurrent feeds, Mode: {PROCESSING_MODE}")

    try:
        with open(CONFIG_FILE_PATH, 'r') as f:
            config = yaml.safe_load(f)
            NEWS_FEEDS = config.get('cybersecurity_news_feeds', [])
            if not NEWS_FEEDS:
                logger.error(f"Could not find 'cybersecurity_news_feeds' in {CONFIG_FILE_PATH} or it's empty.")
                return
    except FileNotFoundError:
        logger.error(f"Configuration file {CONFIG_FILE_PATH} not found.")
        return
    except yaml.YAMLError as e_yaml:
        logger.error(f"Error parsing YAML configuration file {CONFIG_FILE_PATH}: {e_yaml}")
        return
    except Exception as e_conf:
        logger.error(f"An unexpected error occurred while loading configuration: {e_conf}")
        return

    logger.info(f"Found {len(NEWS_FEEDS)} RSS feeds to process")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    # Process feeds concurrently for better performance
    total_inserted_all_feeds = 0
    total_processed_all_feeds = 0
    total_skipped_all_feeds = 0
    successful_feeds = 0
    failed_feeds = 0

    # Use ThreadPoolExecutor for concurrent processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_FEEDS) as executor:
        # Submit all feed processing tasks
        future_to_feed = {
            executor.submit(process_single_feed, feed_info, supabase_client): feed_info
            for feed_info in NEWS_FEEDS
        }

        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_feed, timeout=FEED_TIMEOUT * len(NEWS_FEEDS)):
            feed_info = future_to_feed[future]
            try:
                _, processed_count, inserted_count, skipped_count = future.result(timeout=FEED_TIMEOUT)

                total_processed_all_feeds += processed_count
                total_inserted_all_feeds += inserted_count
                total_skipped_all_feeds += skipped_count

                if processed_count > 0 or inserted_count > 0:
                    successful_feeds += 1
                else:
                    failed_feeds += 1

            except concurrent.futures.TimeoutError:
                logger.error(f"Timeout processing feed: {feed_info.get('name','Unknown')}")
                failed_feeds += 1
            except Exception as e:
                logger.error(f"Exception processing feed {feed_info.get('name','Unknown')}: {e}")
                failed_feeds += 1

    # Calculate processing time
    end_time = datetime.now()
    processing_time = (end_time - start_time).total_seconds()

    # Enhanced summary with performance metrics
    logger.info("=" * 80)
    logger.info("RSS FEED PROCESSING SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total Feeds: {len(NEWS_FEEDS)}")
    logger.info(f"Successful: {successful_feeds}")
    logger.info(f"Failed: {failed_feeds}")
    logger.info(f"Total Items Processed: {total_processed_all_feeds}")
    logger.info(f"Total Items Inserted: {total_inserted_all_feeds}")
    logger.info(f"Total Items Skipped: {total_skipped_all_feeds}")
    logger.info(f"Processing Time: {processing_time:.2f} seconds")
    logger.info(f"Average Speed: {total_processed_all_feeds/processing_time:.1f} items/second"if processing_time > 0 else"Average Speed: N/A")

    # Breach detection summary
    if BREACH_INTELLIGENCE_ENABLED:
        logger.info(f"Breach Intelligence: ENABLED (threshold: {BREACH_CONFIDENCE_THRESHOLD})")
    else:
        logger.info(f"Breach Intelligence: DISABLED")

    logger.info("=" * 80)

    # Performance recommendations
    if processing_time > 300:  # 5 minutes
        logger.warning(f"Processing took {processing_time:.1f}s. Consider reducing MAX_ITEMS_PER_FEED or FILTER_DAYS_BACK")
    elif total_inserted_all_feeds == 0:
        logger.warning("No new items inserted. Check if feeds are working or date filters are too restrictive")
    else:
        logger.info(f"Processing completed successfully! {total_inserted_all_feeds} new items added to database")

if __name__ == "__main__":
    logger.info("Cybersecurity News RSS Feed Scraper Started")
    
    # Check for Supabase env vars first, as they are critical for the script's core function.
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set for Supabase client.")
        # Optionally, print to console if run directly without these, as logger might not be fully configured or visible.
        if __name__ == "__main__":
             print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_cybersecurity_news_feeds() # This function now loads its own config.
        
    logger.info("Cybersecurity News RSS Feed Scraper Finished")
