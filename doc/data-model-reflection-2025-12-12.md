# Data Model Reflection - December 12, 2025

## The Core Question

Is the current Recording/Release model the right approach, or is there a fundamentally different way to think about this?

---

## What Actually Matters (Priority Order)

### 1. Finding Recordings to Study
For any song that might get called at a gig, find a rich set of versions with different approaches:
- What key, what tempo, what instrumentation?
- What do the solos sound like?
- Can I extract bits of solos for my own benefit?

### 2. Highlighting Notable/Canonical Recordings
Specific recordings that serious jazz musicians should know:
- The Coltrane "My Favorite Things"
- The Cannonball/Miles "Autumn Leaves" from Somethin' Else
- These require accurate metadata - knowing *which* recording matters

### 3. Digital Playback
Since it's 2025, being able to actually listen matters:
- Spotify (current focus), Apple Music, YouTube
- The specific recording/players/date matters for jazz study
- The specific physical release (vinyl, CD, box set) does NOT matter
- But keeping links to MusicBrainz/Discogs is useful for provenance

---

## Key Observations

### Coverage Strategy Varies by Tune
- **Obscure tunes** (e.g., "By the River Sainte Marie"): Maybe 40-100 recordings exist. Broad coverage helps surface interesting versions (bebop, guitar solos, etc.)
- **Popular standards** (e.g., "Autumn Leaves", "Summertime"): Thousands exist. Complete coverage is a fool's errand.

### Recording vs Release Granularity
MusicBrainz and Discogs care about distinctions that don't matter for jazz study:
- Stereo vs mono
- Minor edits (last few seconds cut)
- 7" vinyl vs Japanese box set vs limited edition picture vinyl

These matter to collectors/audiophiles. They don't matter for learning a tune.

### The Fingerprinting Problem
At Echo Nest, audio fingerprinting solved deduplication definitively - if two tracks sound the same, they're the same recording. Without access to raw audio or fingerprinting, we're stuck with fuzzy metadata matching.

### Jazz-Specific Complications
- **Specific live recordings** that people reference in jazz lore - finding "that one version" matters
- **Alternate takes** are pedagogically valuable - hearing two Grant Green solos on the same tune with the same band reveals how he approaches the tune
- These look like "duplicates" but are actually features

---

## Current Pain Points

1. **Whack-a-mole matching**: Edge cases in artist credits, track names, release variants keep surfacing
2. **Rate limiting**: Gathering data from external sources is slow
3. **Model complexity**: Trying to maintain traceability to MusicBrainz's full discographic model when we don't need that granularity
4. **Misaligned optimization**: Built infrastructure for a cataloging problem, but solving a discovery/study problem

---

## Alternative Approaches Considered

### 1. Spotify-First (REJECTED)
Start with what's playable on Spotify, enrich from there.

**Why rejected:**
- Spotify label rights change; jazz catalog is not their priority
- Some canonical recordings are only on vinyl
- Need to understand the broader universe, not just what's streamable today

### 2. "Performance" as Core Concept
Jazz musicians think "the 1959 Miles Davis version" not "MusicBrainz recording ID xyz."

A Performance = artist(s) + approximate date + session/venue, with multiple *sources* (Spotify, YouTube, etc.)

**Status:** Conceptually right, but practically the Recording table is already trying to be this. The problem is reliably linking tracks to performances without audio fingerprinting.

### 3. Curation-Forward Workflow (PROMISING)
Accept that automation suggests, human approves. Build review tools rather than better matching heuristics.

### 4. Tiered Data Quality (PROMISING)
- **Tier 1:** Hand-curated notable recordings
- **Tier 2:** High-confidence auto-imports
- **Tier 3:** Everything else

---

## Potential Path Forward: Curation Layer

Keep the current model (Recording ≈ Performance), but add a curation layer:

### Schema Additions
1. **`curated` flag** on recordings and/or recording_releases
   - Once verified, stamp it
   - Auto-importers respect the stamp and don't overwrite

2. **`notable` flag** (separate from curated)
   - Canonical recordings worth highlighting
   - Drives UI prominence, "essential recordings" lists

### Workflow Changes
1. Auto-import freely for non-curated records
2. For curated records: suggest changes but don't apply automatically
3. Review queue for "importer wants to change curated data"
4. Audit tools skip/separate curated records

### Mindset Shift
Move from "fix matching bugs" to "review and stamp records you care about" - which aligns better with the actual goal.

---

## Open Questions

- Is the Recording/Release junction still the right place to store Spotify track IDs?
- Should "notable" be a boolean or something richer (notes, why it's notable)?
- How to handle the case where a curated recording's Spotify track disappears?
- What's the right UI for the curation workflow?

---

## Next Steps (When Ready)

1. Decide if the curation layer approach feels right
2. Sketch schema changes (`curated_at`, `notable`, etc.)
3. Modify importers to respect curated flags
4. Build review/approval workflow for curated data
