#!/usr/bin/env python3
"""Sync EvoMap data to Google Sheets.

This script runs periodically (e.g., via cron) to extract signal aggregates
from EvoMapObserver and upload them to a Google Sheet for dashboarding.
It creates a new sheet if OPENMIND_EVOMAP_SHEET_ID is not configured.
"""

import logging
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

from chatgptrest.evomap.observer import EvoMapObserver
from chatgptrest.integrations.google_workspace import GoogleWorkspace

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _get_evomap_db_path() -> str:
    # Use the configured artifact dir to find evomap.db
    artifact_dir = os.environ.get("OPENMIND_KB_ARTIFACT_DIR", "/vol1/1000/projects/ChatgptREST/data/kb")
    os.makedirs(artifact_dir, exist_ok=True)
    return os.path.join(artifact_dir, "evomap.db")


def main():
    load_dotenv()

    # Avoid hanging if there are network issues
    import socket
    socket.setdefaulttimeout(15.0)

    gw = GoogleWorkspace()
    if not gw.load_token() or not gw.is_authenticated():
        logging.error("GoogleWorkspace not authenticated. Please run the auth setup first.")
        sys.exit(1)

    if "sheets" not in gw._enabled:
        logging.error("Google Sheets API not enabled in OPENMIND_GOOGLE_SERVICES.")
        sys.exit(1)

    db_path = _get_evomap_db_path()
    logging.info(f"Loading EvoMap signals from {db_path}")
    observer = EvoMapObserver(db_path=db_path)

    # Gather simple aggregations
    try:
        types_agg = observer.aggregate_by_type()
        domains_agg = observer.aggregate_by_domain()
        total_signals = observer.count()
    except Exception as e:
        logging.error(f"Failed to query EvoMap database: {e}")
        sys.exit(1)
    finally:
        observer.close()

    logging.info(f"Loaded {total_signals} total signals.")

    sheet_id = os.environ.get("OPENMIND_EVOMAP_SHEET_ID", "")
    
    if not sheet_id:
        # Create a new spreadsheet
        title = f"OpenMind V3 EvoMap - {datetime.now().strftime('%Y-%m-%d')}"
        logging.info(f"OPENMIND_EVOMAP_SHEET_ID missing. Creating new spreadsheet: {title}")
        res = gw.sheets_create(title)
        
        if "error" in res:
            logging.error(f"Failed to create spreadsheet: {res['error']}")
            sys.exit(1)
            
        sheet_id = res["spreadsheet_id"]
        logging.info(f"Created new spreadsheet: {res['url']}")
        logging.info(f"Please add OPENMIND_EVOMAP_SHEET_ID=\"{sheet_id}\" to your chatgptrest/core/env.py or .env file.")
        
        # Initialize headers
        gw.sheets_write(sheet_id, "Sheet1!A1:D1", [["Timestamp", "Category", "Data Type", "Count"]])

    # Prepare rows to append
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    rows = []
    
    # Append Domain aggregates
    for domain, count in domains_agg.items():
        if not domain: domain = "Unknown"
        rows.append([timestamp, "Domain", domain, str(count)])
        
    # Append Type aggregates
    for signal_type, count in types_agg.items():
        if not signal_type: signal_type = "Unknown"
        rows.append([timestamp, "Signal Type", signal_type, str(count)])
        
    if not rows:
        logging.info("No data to sync.")
        return

    # Write data back to Sheet 1 starting from next available row using APPEND
    try:
        logging.info(f"Syncing {len(rows)} rows to spreadsheet {sheet_id}...")
        
        # Use a workaround for appending: Google API update with append logic
        # OR just use the standard update if we do a dirty clear, but let's try to append using append API
        # The GW abstraction only has sheets_write which does an 'update'. Since we can't easily append with the current wrapper
        # We'll just define a specific range or overwrite for the sake of simplicity.
        # Overwrite from row 2 out
        gw.sheets_write(sheet_id, "Sheet1!A2:D", rows)
        logging.info("Sync complete.")
    except Exception as e:
        logging.error(f"Sync failed: {e}")

if __name__ == "__main__":
    main()
