# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

JazzReference is a reference application for jazz music study, consisting of:
- **Backend**: Flask API (Python 3.13) serving data from PostgreSQL
- **iOS App**: SwiftUI app for browsing jazz standards, performers, and recordings

The API is deployed at `https://www.approachnote.com/api`.

## Development Commands

### Backend

```bash
# Setup
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run locally (port 5001, includes research worker)
python app.py

# Run with gunicorn (production-like)
gunicorn -c gunicorn.conf.py app:app
```

### iOS App

Open `iOS-app/JazzReference.xcodeproj` in Xcode. The app targets iOS and uses SwiftUI.

## Architecture

### Backend Structure

```
backend/
├── app.py              # Flask app entry point, blueprint registration
├── config.py           # Logging and app configuration
├── db_utils.py         # PostgreSQL connection pooling (psycopg3)
├── routes/             # API route blueprints
│   ├── songs.py        # /api/songs endpoints
│   ├── recordings.py   # /api/recordings endpoints
│   ├── performers.py   # /api/performers endpoints
│   ├── repertoires.py  # /api/repertoires (auth-protected)
│   ├── transcriptions.py
│   ├── auth.py         # JWT authentication
│   ├── password.py     # Password reset flow
│   └── ...
├── research_queue.py   # Background worker queue for data enrichment
├── song_research.py    # Orchestrates MusicBrainz + Spotify imports
├── mb_*.py             # MusicBrainz API utilities and importers
├── spotify_*.py        # Spotify API utilities and matching
├── caa_*.py            # Cover Art Archive utilities
├── wiki_utils.py       # Wikipedia data extraction
└── scripts/            # Data import/maintenance scripts
```

### Key Backend Patterns

- **Blueprint Registration**: All routes in `routes/__init__.py` via `register_blueprints()`
- **Connection Pooling**: Uses psycopg3 connection pool; set `DB_USE_POOLING=true` before importing `db_utils`
- **Background Worker**: `research_queue` runs in-process thread for async data enrichment
- **JWT Auth**: `auth_utils.py` provides `@token_required` decorator for protected endpoints

### iOS App Structure

```
iOS-app/JazzReference/
├── JazzReferenceApp.swift    # App entry point, deep link handling
├── Support_Files/
│   ├── NetworkManager.swift  # API client (async/await)
│   ├── Models.swift          # Data models
│   └── JazzTheme.swift       # UI theming
├── Auth/
│   ├── AuthenticationManager.swift
│   └── Views/                # Login, Register, ForgotPassword
├── *ListView.swift           # List views (Songs, Artists, Recordings)
├── *DetailView.swift         # Detail views
└── RepertoireManager.swift   # User repertoire state
```

### Database Schema

Core tables (see `sql/jazz-db-schema.sql`):
- `songs` - Jazz standards with MusicBrainz work IDs
- `recordings` - Specific recordings linked to songs
- `performers` - Artists with MusicBrainz artist IDs
- `releases` - MusicBrainz releases with cover art
- `recording_performers` - Junction table with instrument roles
- `users` - Authentication (email/password, Google, Apple)
- `repertoires` / `repertoire_songs` - User song collections

### External Data Sources

- **MusicBrainz**: Work IDs, recording metadata, performer credits, releases
- **Spotify**: Track matching, album art, streaming links
- **Cover Art Archive**: Album artwork via MusicBrainz release IDs
- **Wikipedia**: Artist biographies, song background info

### Data Flow

1. Songs/performers added via admin scripts or iOS share extension
2. `research_queue` triggers background import from MusicBrainz
3. `spotify_matcher` matches recordings to Spotify tracks
4. `caa_release_importer` fetches cover art for releases
5. iOS app fetches enriched data via REST API

## Environment Variables

Backend requires `.env` with:
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET_KEY` - For authentication tokens
- `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` - Spotify API
- `SENDGRID_API_KEY` - For password reset emails
