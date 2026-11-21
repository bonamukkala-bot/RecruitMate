#!/usr/bin/env python3
"""
Standalone retention purge script.
Removes candidates older than each company's configured data_retention_days.

Usage:
    python scripts/purge_expired.py              # DRY-RUN (default)
    python scripts/purge_expired.py --execute    # Permanent deletion
    python scripts/purge_expired.py --company-id <id> --execute
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import Config
from utils.retention import purge_expired_candidates

def main():
    parser = argparse.ArgumentParser(description="Purge candidates older than company retention periods.")
    parser.add_argument("--execute", action="store_true", help="Perform permanent deletion (default is dry-run)")
    parser.add_argument("--company-id", type=str, default=None, help="Target a specific company ID")
    args = parser.parse_args()

    # Safety Guard: refuse to run against production database unless explicit env override is provided
    if Config.DB_NAME == "recruitmate" and os.getenv("ALLOW_PROD_PURGE", "").lower() != "true":
        raise RuntimeError(
            "Operation prohibited: Connected to production database 'recruitmate'! "
            "Set environment variable ALLOW_PROD_PURGE=true to override."
        )

    print(f"🔒 Database: {Config.DB_NAME}")
    print(f"⚙️  Mode: {'PERMANENT DELETION (--execute)' if args.execute else 'DRY RUN (Preview)'}")
    if args.company_id:
        print(f"🎯 Target Company: {args.company_id}")

    res = purge_expired_candidates(company_id=args.company_id, execute=args.execute)

    print(f"\n📊 Summary:")
    print(f"  • Candidates Found Expired : {res['candidates_found']}")
    print(f"  • Candidates Purged        : {res['candidates_purged']}")
    print(f"  • Mode                     : {'Executed' if res['execute'] else 'Dry Run'}")

    for comp in res.get("companies", []):
        print(f"    - Company {comp['company_id']}: retention={comp['retention_days']}d, "
              f"found={comp['candidates_found']}, purged={comp['candidates_purged']}")

    if not args.execute and res['candidates_found'] > 0:
        print("\n💡 To permanently delete these records, re-run with --execute.")

if __name__ == "__main__":
    main()
