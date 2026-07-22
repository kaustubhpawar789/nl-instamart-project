-- Swiggy Instamart Discovery Engine — Postgres Schema
-- Run: psql $DATABASE_URL -f database/schema.sql

BEGIN;

-- ── Reviews (live scraped + cleaned feedback) ──
CREATE TABLE IF NOT EXISTS reviews (
    id              TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    date            DATE,
    platform        TEXT,
    user_name       TEXT,
    location        TEXT,
    text            TEXT NOT NULL,
    intent          TEXT NOT NULL CHECK (intent IN ('complaint','suggestion','praise','observation','question')),
    categories      TEXT[] NOT NULL DEFAULT '{}',
    rating          INTEGER CHECK (rating BETWEEN 1 AND 5),
    url             TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reviews_intent ON reviews(intent);
CREATE INDEX IF NOT EXISTS idx_reviews_source ON reviews(source);
CREATE INDEX IF NOT EXISTS idx_reviews_date ON reviews(date);
CREATE INDEX IF NOT EXISTS idx_reviews_categories ON reviews USING GIN(categories);

-- ── Themes (from AI extraction) ──
CREATE TABLE IF NOT EXISTS themes (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    frequency       TEXT NOT NULL CHECK (frequency IN ('High','Medium','Low')),
    mentions        INTEGER NOT NULL,
    sentiment_pos   INTEGER DEFAULT 0,
    sentiment_neu   INTEGER DEFAULT 0,
    sentiment_neg   INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Theme evidence quotes ──
CREATE TABLE IF NOT EXISTS theme_evidence (
    id              SERIAL PRIMARY KEY,
    theme_id        INTEGER NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
    quote           TEXT NOT NULL,
    source          TEXT NOT NULL,
    category        TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evidence_theme ON theme_evidence(theme_id);

-- ── Theme blockers ──
CREATE TABLE IF NOT EXISTS theme_blockers (
    id              SERIAL PRIMARY KEY,
    theme_id        INTEGER NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
    blocker         TEXT NOT NULL
);

-- ── Theme triggers ──
CREATE TABLE IF NOT EXISTS theme_triggers (
    id              SERIAL PRIMARY KEY,
    theme_id        INTEGER NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
    trigger_text    TEXT NOT NULL
);

-- ── Theme-category mapping ──
CREATE TABLE IF NOT EXISTS theme_categories (
    theme_id        INTEGER NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
    category        TEXT NOT NULL,
    PRIMARY KEY (theme_id, category)
);

-- ── Insights (structured) ──
CREATE TABLE IF NOT EXISTS insights (
    id              SERIAL PRIMARY KEY,
    title           TEXT NOT NULL UNIQUE,
    observation     TEXT NOT NULL,
    user_need       TEXT NOT NULL,
    root_cause      TEXT NOT NULL,
    opportunity     TEXT NOT NULL,
    implication     TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Categories priority matrix ──
CREATE TABLE IF NOT EXISTS categories (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    mentions        INTEGER NOT NULL,
    gap_severity    TEXT NOT NULL CHECK (gap_severity IN ('High','Medium','Low')),
    business_impact TEXT NOT NULL CHECK (business_impact IN ('High','Medium','Low')),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Sentiment summary ──
CREATE TABLE IF NOT EXISTS sentiment (
    id              SERIAL PRIMARY KEY CHECK (id = 1),
    positive_count  INTEGER NOT NULL,
    positive_pct    NUMERIC(5,1) NOT NULL,
    neutral_count   INTEGER NOT NULL,
    neutral_pct     NUMERIC(5,1) NOT NULL,
    negative_count  INTEGER NOT NULL,
    negative_pct    NUMERIC(5,1) NOT NULL,
    total_reviews   INTEGER NOT NULL,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Research validation data ──
CREATE TABLE IF NOT EXISTS research_data (
    id              SERIAL PRIMARY KEY,
    respondent_id   TEXT NOT NULL UNIQUE,
    summary         TEXT NOT NULL,
    matched_themes  TEXT[] NOT NULL DEFAULT '{}',
    quality_score   INTEGER NOT NULL CHECK (quality_score BETWEEN 0 AND 100),
    recommendation  TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

COMMIT;
