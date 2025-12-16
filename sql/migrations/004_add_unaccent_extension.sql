-- Migration: Add unaccent extension for accent-insensitive text matching
-- This enables matching "Mel Torme" to "Mel Tormé" in the database

CREATE EXTENSION IF NOT EXISTS unaccent;
