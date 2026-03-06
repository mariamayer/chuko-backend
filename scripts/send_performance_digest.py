#!/usr/bin/env python3
"""
Send weekly performance digest email — manual only for now.

Trigger manually via:
  cd backend && python -m scripts.send_performance_digest

Or via the dashboard Agents page → "Send digest email" button.

To automate later, add a cron entry (every Monday at 9am):
  0 9 * * 1 cd /path/to/merch-ai/backend && python -m scripts.send_performance_digest
"""

import os
import sys

# Add parent directory to path so lib/ imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from lib.performance_digest import send_digest

if __name__ == "__main__":
    ok, msg = send_digest()
    print(msg)
    sys.exit(0 if ok else 1)
