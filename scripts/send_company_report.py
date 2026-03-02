#!/usr/bin/env python3
"""
Send company report email - run via cron every 2 weeks.

Usage:
  cd backend && python -m scripts.send_company_report

Cron example (every 2 weeks on Monday at 9am):
  0 9 * * 1 [ $(($(date +\%s) / 604800 \% 2)) -eq 0 ] && cd /path/to/merch-ai/backend && python -m scripts.send_company_report

Simpler: run every 14 days (e.g. 1st and 15th at 9am):
  0 9 1,15 * * cd /path/to/merch-ai/backend && python -m scripts.send_company_report
"""

import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from lib.reports import send_company_report

if __name__ == "__main__":
    ok, msg = send_company_report()
    print(msg)
    sys.exit(0 if ok else 1)
