#!/usr/bin/env python3
"""
scripts/auto_cleanup.py — DB-012: 5-Minute Inactivity Auto-Cleanup
Tracks API request timestamps and truncates dynamic PostgreSQL tables
after 5 minutes of inactivity. Core schema tables are preserved.

Usage (imported by api_server.py, tested by tests/test_db_012_cleanup.py):
    from scripts import auto_cleanup
    auto_cleanup.set_last_request_time()
    auto_cleanup.start_cleanup_monitor()
    auto_cleanup.truncate_dynamic_tables()
"""

import os
import sys
import time
import threading
from datetime import datetime, timezone
from dotenv import load_dotenv
import psycopg2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, "secrets", ".env"))


# ── Tables ────────────────────────────────────────────────────────────────

DYNAMIC_TABLES = [
    "users",
    "products",
    "recommendations",
    "feedback",
    "tickets",
    "test_data",
    "workflow_outputs",
    "reviews",
    "themes",
    "theme_evidence",
    "theme_blockers",
    "theme_triggers",
    "theme_categories",
    "insights",
    "sentiment",
    "research_data",
    "user_carts",
]

PRESERVED_TABLES = [
    "categories",
]


# ── Database connection ───────────────────────────────────────────────────

def get_connection(autocommit=False):
    from database.db import get_db_connection
    return get_db_connection(autocommit=autocommit)


# ── Inactivity tracker ────────────────────────────────────────────────────

_last_request_time = time.time()
_tracker_lock = threading.Lock()
INACTIVITY_TIMEOUT = 300  # 5 minutes in seconds
_MONITOR_INTERVAL = 30    # check every 30 seconds


def set_last_request_time():
    with _tracker_lock:
        global _last_request_time
        _last_request_time = time.time()


def get_last_request_time():
    with _tracker_lock:
        return _last_request_time


def seconds_since_last_request():
    return time.time() - get_last_request_time()


# ── Truncation ────────────────────────────────────────────────────────────

_truncate_lock = threading.Lock()


def truncate_dynamic_tables():
    if not _truncate_lock.acquire(blocking=False):
        print("[auto_cleanup] Truncation already in progress, skipping")
        return False

    try:
        conn = get_connection(autocommit=True)
        cur = conn.cursor()

        table_list = ", ".join(DYNAMIC_TABLES)
        print(f"[auto_cleanup] Truncating dynamic tables: {table_list}")
        cur.execute(f"TRUNCATE TABLE {table_list} CASCADE;")
        print("[auto_cleanup] Truncation complete")

        for table in DYNAMIC_TABLES:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"[auto_cleanup]   {table}: {count} rows (should be 0)")

        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[auto_cleanup] Truncation error: {e}")
        return False
    finally:
        _truncate_lock.release()


# ── Background monitor ────────────────────────────────────────────────────

_monitor_started = False
_monitor_lock = threading.Lock()


def start_cleanup_monitor():
    global _monitor_started
    with _monitor_lock:
        if _monitor_started:
            return
        _monitor_started = True

    def _loop():
        print(f"[auto_cleanup] Monitor started (timeout={INACTIVITY_TIMEOUT}s, interval={_MONITOR_INTERVAL}s)")
        while True:
            time.sleep(_MONITOR_INTERVAL)
            idle = seconds_since_last_request()
            if idle >= INACTIVITY_TIMEOUT:
                print(f"[auto_cleanup] {idle:.0f}s idle — triggering cleanup")
                truncate_dynamic_tables()

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    print("[auto_cleanup] Cleanup monitor daemon thread launched")
