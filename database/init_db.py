#!/usr/bin/env python3
"""
database/init_db.py — Phase 2 PostgreSQL Schema Initialization
Creates the instamart database and all required tables.

Usage:
    source .venv/bin/activate
    python database/init_db.py
"""

import os
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, "secrets", ".env"))


def get_db_params():
    return {
        "dbname": os.getenv("DB_NAME", "instamart"),
        "user": os.getenv("DB_USER", "nitin"),
        "password": os.getenv("DB_PASSWORD", "nitin"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
    }


def create_database_if_missing():
    params = get_db_params()
    conn = psycopg2.connect(
        host=params["host"],
        port=params["port"],
        user=params["user"],
        password=params["password"],
        dbname="postgres",
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (params["dbname"],))
    if not cur.fetchone():
        cur.execute(f"CREATE DATABASE {params['dbname']}")
        print(f"  + Created database '{params['dbname']}'")
    else:
        print(f"  · Database '{params['dbname']}' already exists")
    cur.close()
    conn.close()


def get_connection():
    params = get_db_params()
    return psycopg2.connect(**params)


PHASE2_SCHEMA = """
BEGIN;

-- ══════════════════════════════════════════════════════════════════════
-- PHASE 2 TABLES
-- ══════════════════════════════════════════════════════════════════════

-- 1. USERS
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    email       TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    phone       TEXT,
    city        TEXT,
    state       TEXT,
    age_group   TEXT CHECK (age_group IN ('18-24','25-34','35-44','45-54','55+')),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_city ON users(city);

-- 2. CATEGORIES (extend Phase 1)
ALTER TABLE categories ADD COLUMN IF NOT EXISTS sub_category TEXT;
ALTER TABLE categories ADD COLUMN IF NOT EXISTS image_url TEXT;
ALTER TABLE categories ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0;
ALTER TABLE categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- 3. PRODUCTS
CREATE TABLE IF NOT EXISTS products (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    category_id     INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    brand           TEXT,
    price           NUMERIC(10,2) NOT NULL CHECK (price > 0),
    mrp             NUMERIC(10,2),
    stock_quantity  INTEGER DEFAULT 0 CHECK (stock_quantity >= 0),
    description     TEXT,
    image_url       TEXT,
    sku             TEXT UNIQUE,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand);
CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active);

-- 4. RECOMMENDATIONS
CREATE TABLE IF NOT EXISTS recommendations (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    score       NUMERIC(5,4) NOT NULL CHECK (score BETWEEN 0 AND 1),
    reason      TEXT,
    algorithm   TEXT NOT NULL DEFAULT 'collaborative_filtering',
    is_clicked  BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recs_user ON recommendations(user_id);
CREATE INDEX IF NOT EXISTS idx_recs_product ON recommendations(product_id);
CREATE INDEX IF NOT EXISTS idx_recs_score ON recommendations(score DESC);

-- 5. FEEDBACK
CREATE TABLE IF NOT EXISTS feedback (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    product_id    INTEGER REFERENCES products(id) ON DELETE SET NULL,
    rating        INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment       TEXT,
    feedback_type TEXT CHECK (feedback_type IN ('product','delivery','app_experience','support')),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_product ON feedback(product_id);
CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback(rating);

-- 6. TICKETS
CREATE TABLE IF NOT EXISTS tickets (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    subject     TEXT NOT NULL,
    description TEXT,
    status      TEXT DEFAULT 'open' CHECK (status IN ('open','in_progress','resolved','closed')),
    priority    TEXT DEFAULT 'medium' CHECK (priority IN ('low','medium','high','urgent')),
    category    TEXT,
    assigned_to TEXT,
    resolved_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);

-- 7. TEST_DATA
CREATE TABLE IF NOT EXISTS test_data (
    id              SERIAL PRIMARY KEY,
    test_name       TEXT NOT NULL,
    test_type       TEXT CHECK (test_type IN ('unit','integration','e2e','performance')),
    input_data      JSONB,
    expected_output JSONB,
    actual_output   JSONB,
    status          TEXT DEFAULT 'pending' CHECK (status IN ('pending','passed','failed','skipped')),
    duration_ms     INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_test_data_type ON test_data(test_type);
CREATE INDEX IF NOT EXISTS idx_test_data_status ON test_data(status);

-- 8. WORKFLOW_OUTPUTS
CREATE TABLE IF NOT EXISTS workflow_outputs (
    id              SERIAL PRIMARY KEY,
    workflow_name   TEXT NOT NULL,
    trigger_source  TEXT,
    input_params    JSONB,
    output_data     JSONB,
    status          TEXT DEFAULT 'pending' CHECK (status IN ('pending','running','completed','failed')),
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_name ON workflow_outputs(workflow_name);
CREATE INDEX IF NOT EXISTS idx_workflow_status ON workflow_outputs(status);

COMMIT;
"""


def init_schema():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(PHASE2_SCHEMA)
    conn.commit()
    cur.close()
    conn.close()


def verify_tables():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' ORDER BY table_name
    """)
    tables = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return tables


def main():
    print("── DB-005: Phase 2 PostgreSQL Setup ─" + "─" * 38)

    print("\n  Creating database if missing...")
    create_database_if_missing()

    print("  Applying Phase 2 schema...")
    init_schema()

    print("  Verifying tables...")
    tables = verify_tables()
    phase2_tables = [
        "users", "products", "categories", "recommendations",
        "feedback", "tickets", "test_data", "workflow_outputs",
    ]
    phase1_tables = [
        "reviews", "themes", "theme_evidence", "theme_blockers",
        "theme_triggers", "theme_categories", "insights", "sentiment",
        "research_data",
    ]
    all_required = phase1_tables + phase2_tables

    print(f"\n  Tables found ({len(tables)}):")
    for t in tables:
        marker = "  ✓" if t in all_required else "  ·"
        print(f"    {marker} {t}")

    missing = [t for t in all_required if t not in tables]
    if missing:
        print(f"\n  ✗ Missing tables: {', '.join(missing)}")
        sys.exit(1)

    print(f"\n  ✓ All {len(phase2_tables)} Phase 2 tables ready")
    print(f"  ✓ All {len(phase1_tables)} Phase 1 tables present")
    print("─" * 58)


if __name__ == "__main__":
    main()
