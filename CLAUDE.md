# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

JazzReference is a reference application for jazz music study, consisting of:
- **Backend**: Flask API (Python 3.13) serving data from PostgreSQL
- **iOS/Mac Apps**: SwiftUI apps for browsing jazz standards, performers, and recordings

The API is deployed at `https://api.approachnote.com`.

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

Open `apps/Approach Note.xcodeproj` in Xcode. The app targets iOS and macOS, using SwiftUI.

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
├── song_research.py    # Orchestrates MusicBrainz + Spotify + Apple Music imports
├── mb_*.py             # MusicBrainz API utilities and importers
├── spotify_*.py        # Spotify API utilities and matching
├── apple_music_*.py    # Apple Music API/Feed utilities and matching
├── caa_*.py            # Cover Art Archive utilities
├── wiki_utils.py       # Wikipedia data extraction
└── scripts/            # Data import/maintenance scripts
```

### Key Backend Patterns

- **Blueprint Registration**: All routes in `routes/__init__.py` via `register_blueprints()`
- **Connection Pooling**: Uses psycopg3 connection pool; set `DB_USE_POOLING=true` before importing `db_utils`
- **Background Worker**: `research_queue` runs in-process thread for async data enrichment
- **JWT Auth**: `auth_utils.py` provides `@token_required` decorator for protected endpoints

### Apps Structure

The `apps/` directory contains iOS, macOS, and shared code:

```
apps/
├── Shared/                      # Code shared between iOS and Mac
│   ├── Auth/
│   │   ├── AuthenticationManager.swift
│   │   ├── KeychainHelper.swift
│   │   └── Models/User.swift
│   ├── Managers/
│   │   ├── FavoritesManager.swift
│   │   └── RepertoireManager.swift
│   └── Support/
│       ├── Models.swift         # Data models
│       ├── NetworkManager.swift # API client (async/await)
│       ├── JazzTheme.swift      # UI theming
│       ├── HelperViews.swift
│       └── PreviewHelpers.swift # SwiftUI preview data
├── iOS/                         # iOS-specific code
│   ├── App/
│   │   └── JazzReferenceApp.swift
│   ├── Auth/Views/              # iOS auth views
│   ├── Components/              # Reusable UI components
│   ├── Managers/                # iOS-only managers
│   ├── Support/                 # iOS-only support (CachedAsyncImage, Toast)
│   └── Views/                   # iOS views
├── Mac/                         # macOS-specific code
│   ├── App/
│   │   └── JazzReferenceMacApp.swift
│   ├── Auth/                    # Mac auth views
│   └── Views/                   # Mac views
└── MusicBrainzImporter/         # Share extension
```

### Model Changes Checklist

When adding or modifying fields in `Shared/Support/Models.swift`:
1. Update the struct definition with the new field
2. Update the `CodingKeys` enum if the API field name differs
3. **Update `Shared/Support/PreviewHelpers.swift`** - add the new field to ALL preview instances of that model (e.g., `Recording.preview1`, `Recording.preview2`, `Recording.previewMinimal`)

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
- **Apple Music**: Track matching, album art via Feed API (bulk catalog) or iTunes Search API
- **Cover Art Archive**: Album artwork via MusicBrainz release IDs
- **Wikipedia**: Artist biographies, song background info

### Data Flow

1. Songs/performers added via admin scripts or iOS share extension
2. `research_queue` triggers background import from MusicBrainz
3. `spotify_matcher` matches recordings to Spotify tracks
4. `apple_music_matcher` matches recordings to Apple Music tracks
5. `caa_release_importer` fetches cover art for releases
6. iOS app fetches enriched data via REST API

## Environment Variables

Backend requires `.env` with:
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET_KEY` - For authentication tokens
- `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` - Spotify API
- `SENDGRID_API_KEY` - For password reset emails

### Apple Music Feed (Optional - for bulk catalog matching)

The Apple Music matcher can use either:
1. **Local catalog** (recommended) - Downloaded via Apple Music Feed API, no rate limits
2. **iTunes Search API** - Free public API but has aggressive rate limiting

To use the Feed API for downloading the full Apple Music catalog:

1. Requires Apple Developer Program membership ($99/year)
2. Create a Media ID in App Store Connect:
   - Go to Users and Access → Integrations → Media API
   - Create a new key and download the .p8 file
3. Set environment variables:
   - `APPLE_MEDIA_ID` - Your Media ID
   - `APPLE_PRIVATE_KEY_PATH` - Path to your .p8 private key file
   - `APPLE_KEY_ID` - The Key ID shown in App Store Connect
   - `APPLE_TEAM_ID` - Your Team ID (Account → Membership)
4. Download the catalog:
   ```bash
   python scripts/download_apple_catalog.py --feed albums
   python scripts/download_apple_catalog.py --feed songs
   ```

Without Feed API credentials, the matcher falls back to the iTunes Search API.
