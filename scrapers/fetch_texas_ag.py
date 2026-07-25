"""
Texas AG 'Data Security Breach Reports' scraper
Uses Playwright to extract data from JavaScript-rendered table with date sorting
Runs fine in GitHub Actions or any cron box (< 10 s per run)
"""
import os
import logging
import asyncio
from datetime import datetime, date, timedelta
from dateutil import parser as dateutil_parser

# Playwright imports
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logging.warning("Playwright not available. Install with: pip install playwright")

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
TEXAS_AG_BREACH_URL = "https://oag.my.site.com/datasecuritybreachreport/apex/DataSecurityReportsPage"
SOURCE_ID_TEXAS_AG = 37  # Texas AG source ID

# Configuration for date filtering
# Default to 30 days back to capture recent breaches (Texas AG updates are not daily)
default_date = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
FILTER_FROM_DATE = os.environ.get("TX_AG_FILTER_FROM_DATE", default_date)

# Processing mode configuration
PROCESSING_MODE = os.environ.get("TX_AG_PROCESSING_MODE", "ENHANCED")  # BASIC, ENHANCED

# Browser timeout configuration
PAGE_TIMEOUT = 30000  # 30 seconds
WAIT_TIMEOUT = 15000  # 15 seconds for table loading

async def scrape_with_playwright(since_date: date | None = None) -> list:
    """
    Use Playwright to scrape Texas AG breach data by executing JavaScript with date sorting.
    This bypasses the guest user API restrictions and sorts by date for faster processing.
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("Playwright is not available. Install with: pip install playwright")
        logger.error("Then run: playwright install chromium")
        return []

    logger.info(f"Using Playwright to scrape Texas AG portal (since: {since_date})...")

    try:
        async with async_playwright() as p:
            # Launch browser in headless mode for CI/CD compatibility
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']  # GitHub Actions compatibility
            )

            # Create a new page
            page = await browser.new_page()

            # Set user agent
            await page.set_extra_http_headers({
                'User-Agent': 'TexasBreachBot/1.0 (+https://github.com/breach-dashboard)'
            })

            # Navigate to the Texas AG portal
            logger.info(f"Navigating to {TEXAS_AG_BREACH_URL}")
            await page.goto(TEXAS_AG_BREACH_URL, wait_until='networkidle', timeout=PAGE_TIMEOUT)

            # Wait for the table to load (it's populated by JavaScript)
            logger.info("Waiting for breach data table to load...")
            try:
                # Wait for table with data (not just headers)
                await page.wait_for_selector('table tbody tr', timeout=WAIT_TIMEOUT)
                logger.info("Table loaded successfully")
            except Exception as e:
                logger.warning(f"Table loading timeout: {e}")
                # Try to proceed anyway in case data is there

            # Click the date column to sort by newest first
            logger.info("Clicking date column to sort by newest data first...")
            try:
                # Click the specific date column header to get newest data
                await page.click('th.sorting_desc[aria-label*="Date Published at OAG Website"]')
                await page.wait_for_timeout(3000)
                logger.info("Successfully clicked date column to sort by newest data")

                # Verify the sort worked by checking the aria-sort attribute
                new_sort_status = await page.evaluate("""
                    () => {
                        const dateHeader = document.querySelector('th[aria-label*="Date Published"]');
                        return dateHeader ? {
                            ariaSort: dateHeader.getAttribute('aria-sort'),
                            ariaLabel: dateHeader.getAttribute('aria-label'),
                            classes: dateHeader.className
                        } : null;
                    }
                """)

                if new_sort_status:
                    logger.info(f"After clicking - Sort status: {new_sort_status}")

            except Exception as e:
                logger.warning(f"Error clicking date column: {e}")
                # Try alternative selector
                try:
                    await page.click('th[aria-controls="mycdrs"][aria-label*="Date Published"]')
                    await page.wait_for_timeout(3000)
                    logger.info("Successfully clicked date column using alternative selector")
                except Exception as e2:
                    logger.warning(f"Alternative selector also failed: {e2}")

            # Check pagination info and verify we have the newest data
            try:
                pagination_info = await page.locator('text=Showing').first.text_content()
                logger.info(f"Pagination info: {pagination_info}")

                # Check what dates we have on the current page after sorting
                current_page_dates = await page.evaluate("""
                    () => {
                        const table = document.querySelector('table');
                        if (!table) return [];

                        const rows = table.querySelectorAll('tbody tr');
                        const dates = [];
                        for (let i = 0; i < Math.min(5, rows.length); i++) {
                            const cells = rows[i].querySelectorAll('td');
                            if (cells.length >= 10) {
                                dates.push(cells[9]?.textContent?.trim() || 'No date');
                            }
                        }
                        return dates;
                    }
                """)

                logger.info(f"Current page sample dates after sorting: {current_page_dates}")

            except Exception as e:
                logger.info(f"Could not find pagination info: {e}")

            # Extract table data with date filtering
            logger.info("Extracting breach data from table...")
            since_date_str = since_date.isoformat() if since_date else None

            breach_data = await page.evaluate(f"""
                (sinceDateStr) => {{
                    const table = document.querySelector('table');
                    if (!table) return {{ data: [], dateInfo: {{ total: 0, filtered: 0, dateRange: '' }} }};

                    const rows = table.querySelectorAll('tbody tr');
                    const data = [];
                    let totalRows = 0;
                    let filteredRows = 0;
                    let oldestDate = null;
                    let newestDate = null;

                    for (const row of rows) {{
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 10) {{
                            totalRows++;
                            const publishedDate = cells[9]?.textContent?.trim() || '';

                            // Track date range
                            if (publishedDate) {{
                                const recordDate = new Date(publishedDate);
                                if (!isNaN(recordDate.getTime())) {{
                                    if (!oldestDate || recordDate < oldestDate) oldestDate = recordDate;
                                    if (!newestDate || recordDate > newestDate) newestDate = recordDate;
                                }}
                            }}

                            // If we have a date filter, check if this record is recent enough
                            if (sinceDateStr) {{
                                try {{
                                    const recordDate = new Date(publishedDate);
                                    const sinceDate = new Date(sinceDateStr);

                                    // Skip records older than our filter date
                                    if (recordDate < sinceDate) {{
                                        filteredRows++;
                                        continue;
                                    }}
                                }} catch (e) {{
                                    // If date parsing fails, include the record
                                }}
                            }}

                            data.push({{
                                'Entity_or_individual_Name__c': cells[0]?.textContent?.trim() || '',
                                'Entity_Address__c': cells[1]?.textContent?.trim() || '',
                                'Entity_City__c': cells[2]?.textContent?.trim() || '',
                                'Entity_State__c': cells[3]?.textContent?.trim() || '',
                                'Entity_Zip__c': cells[4]?.textContent?.trim() || '',
                                'Types_of_Personal_Information__c': cells[5]?.textContent?.trim() || '',
                                'Number_of_Texans_Affected__c': cells[6]?.textContent?.trim() || '',
                                'Notice_Provided__c': cells[7]?.textContent?.trim() || '',
                                'Notice_Methods__c': cells[8]?.textContent?.trim() || '',
                                'Published_Date__c': publishedDate,
                                'Id': `tx_ag_${{Date.now()}}_${{Math.random().toString(36).substr(2, 9)}}`
                            }});
                        }}
                    }}

                    const dateRange = oldestDate && newestDate ?
                        `${{oldestDate.toISOString().split('T')[0]}} to ${{newestDate.toISOString().split('T')[0]}}` :
                        'No valid dates found';

                    return {{
                        data: data,
                        dateInfo: {{
                            total: totalRows,
                            filtered: filteredRows,
                            included: data.length,
                            dateRange: dateRange,
                            filterDate: sinceDateStr
                        }}
                    }};
                }}
            """, since_date_str)

            await browser.close()

            # Extract data and info from the result
            if isinstance(breach_data, dict) and 'data' in breach_data:
                data = breach_data['data']
                date_info = breach_data.get('dateInfo', {})

                # Log detailed extraction information
                logger.info(f"Table analysis complete:")
                logger.info(f"  Total rows in table: {date_info.get('total', 0)}")
                logger.info(f"  Date range in table: {date_info.get('dateRange', 'Unknown')}")
                logger.info(f"  Filter date: {date_info.get('filterDate', 'None')}")
                logger.info(f"  Rows filtered out: {date_info.get('filtered', 0)}")
                logger.info(f"  Records included: {date_info.get('included', 0)}")

                logger.info(f"Successfully extracted {len(data)} breach records using Playwright")
                return data
            else:
                # Fallback for old format
                logger.info(f"Successfully extracted {len(breach_data)} breach records using Playwright")
                return breach_data if isinstance(breach_data, list) else []

    except Exception as e:
        logger.error(f"Error in Playwright scraping: {e}")
        return []

def parse_date_flexible(date_str: str) -> str | None:
    """
    Parse date string to ISO format.
    """
    if not date_str or date_str.strip() == "" or date_str.strip().lower() in ["n/a", "-"]:
        return None

    try:
        # Clean up the date string
        date_str = date_str.strip()

        # Handle MM/DD/YYYY format common in Texas AG portal
        parsed_date = dateutil_parser.parse(date_str)
        return parsed_date.strftime('%Y-%m-%d')
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to parse date '{date_str}': {e}")
        return None

def parse_affected_individuals(count_str: str) -> int | None:
    """
    Parse affected individuals count from string.
    """
    if not count_str or count_str.strip() == "" or count_str.strip().lower() in ["n/a", "-"]:
        return None

    try:
        # Remove commas and convert to int
        count_str = count_str.strip().replace(',', '')
        return int(count_str)
    except (ValueError, TypeError):
        logger.warning(f"Failed to parse affected individuals count '{count_str}'")
        return None

def should_process_breach(publication_date: str) -> bool:
    """
    Check if breach should be processed based on date filtering.
    """
    if not FILTER_FROM_DATE or not publication_date:
        return True

    try:
        filter_date = dateutil_parser.parse(FILTER_FROM_DATE).date()
        pub_date = dateutil_parser.parse(publication_date).date()
        return pub_date >= filter_date
    except (ValueError, TypeError):
        # If date parsing fails, include the item
        return True

def upsert_records(records: list[dict], supabase_client: SupabaseClient) -> tuple[int, int]:
    """
    Upsert breach records to database - adapted for existing schema.
    Returns (inserted_count, skipped_count)
    """
    inserted_count = 0
    skipped_count = 0

    for record in records:
        try:
            # Extract and map fields from Salesforce record
            entity_name = record.get('Entity_or_individual_Name__c', record.get('Name', ''))
            entity_address = record.get('Entity_Address__c', '')
            entity_city = record.get('Entity_City__c', '')
            entity_state = record.get('Entity_State__c', '')
            entity_zip = record.get('Entity_Zip__c', '')
            info_affected = record.get('Types_of_Personal_Information__c', '')
            texans_affected = record.get('Number_of_Texans_Affected__c', '')
            notice_provided = record.get('Notice_Provided__c', '')
            notice_methods = record.get('Notice_Methods__c', '')
            date_published = record.get('Published_Date__c', record.get('CreatedDate', ''))

            # Skip if essential fields are missing
            if not entity_name or not date_published:
                logger.warning(f"Missing essential data for record. Skipping.")
                skipped_count += 1
                continue

            # Parse dates
            publication_date = parse_date_flexible(date_published)
            if not publication_date:
                logger.warning(f"Could not parse publication date '{date_published}' for {entity_name}")
                skipped_count += 1
                continue

            # Apply date filtering
            if not should_process_breach(publication_date):
                logger.debug(f"Skipping {entity_name} - outside date filter range")
                skipped_count += 1
                continue

            # Parse affected individuals count
            affected_individuals = parse_affected_individuals(str(texans_affected))

            # Create item URL (unique identifier)
            item_url = f"{TEXAS_AG_BREACH_URL}#{entity_name.replace(' ', '_')}_{publication_date.replace('-', '_')}"

            # Check if item already exists
            if supabase_client.check_item_exists(item_url):
                logger.debug(f"Item already exists: {entity_name}")
                skipped_count += 1
                continue

            # Prepare raw data
            raw_data = {
                'entity_address': entity_address,
                'entity_city': entity_city,
                'entity_state': entity_state,
                'entity_zip': entity_zip,
                'notice_provided_to_consumers': notice_provided,
                'notice_methods': notice_methods,
                'date_published_at_oag': date_published,
                'portal_url': TEXAS_AG_BREACH_URL,
                'scraping_timestamp': datetime.now().isoformat(),
                'salesforce_id': record.get('Id', ''),
                'full_salesforce_record': record
            }

            # Prepare item data for database
            item_data = {
                'source_id': SOURCE_ID_TEXAS_AG,
                'item_url': item_url,
                'title': entity_name,
                'publication_date': publication_date,
                'reported_date': publication_date,  # Date reported to Texas AG (same as publication date)
                'affected_individuals': affected_individuals,
                'what_was_leaked': info_affected if info_affected and info_affected != '-' else None,
                'raw_data_json': raw_data,
                'tags_keywords': ['texas_ag', 'data_breach', 'state_notification']
            }

            # Insert into database
            result = supabase_client.insert_item(**item_data)
            if result:
                logger.info(f"Inserted: {entity_name} ({affected_individuals or'Unknown'} affected)")
                inserted_count += 1
            else:
                logger.error(f"Failed to insert: {entity_name}")
                skipped_count += 1

        except Exception as e:
            logger.error(f"Error processing record: {e}")
            skipped_count += 1
            continue

    return inserted_count, skipped_count

def process_texas_ag_breaches():
    """
    Main processing function using Playwright to scrape Texas AG breach data.

    This function:
    1. Uses Playwright to execute JavaScript and extract table data
    2. Sorts by date for faster processing of recent breaches
    3. Applies date filtering to only process recent records
    4. Upserts new/changed rows into the database
    """
    logger.info("Starting Texas AG Data Security Breach Reports processing...")
    logger.info(f"Configuration: Filter from {FILTER_FROM_DATE}, Mode: {PROCESSING_MODE}")

    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return

    try:
        # Determine date filter
        since_date = None
        if FILTER_FROM_DATE:
            try:
                since_date = dateutil_parser.parse(FILTER_FROM_DATE).date()
                logger.info(f"Filtering breaches since: {since_date}")
            except (ValueError, TypeError):
                logger.warning(f"Invalid filter date '{FILTER_FROM_DATE}', fetching all records")

        # Use Playwright to scrape breach data with date filtering
        if PLAYWRIGHT_AVAILABLE:
            try:
                # Run Playwright in async context
                breach_records = asyncio.run(scrape_with_playwright(since_date))
            except Exception as e:
                logger.error(f"Playwright scraping failed: {e}")
                breach_records = []
        else:
            logger.error("Playwright not available. Install with: pip install playwright")
            return

        if not breach_records:
            logger.warning("No breach records retrieved from Texas AG portal")
            return

        # Process and upsert records
        logger.info(f"Processing {len(breach_records)} breach records...")
        inserted_count, skipped_count = upsert_records(breach_records, supabase_client)

        logger.info(f"Texas AG processing complete. Inserted: {inserted_count}, Skipped: {skipped_count}")

    except Exception as e:
        logger.error(f"Error in Texas AG breach processing: {e}")
        return

def main():
    """
    Main function for Texas AG scraper.
    """
    logger.info("Texas AG Data Security Breach Scraper Started")

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
        return
    else:
        logger.info("Supabase environment variables are set.")

    process_texas_ag_breaches()

    logger.info("Texas AG Data Security Breach Scraper Finished")

if __name__ == "__main__":
    main()
