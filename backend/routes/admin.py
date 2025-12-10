"""
Admin Routes - Orphan Recording Review

ARCHITECTURE NOTE:
This module handles orphan recording import. To avoid code duplication with
the main MusicBrainz import flow, we reuse:
- MBReleaseImporter: For release creation and CAA cover art import
- PerformerImporter: For linking performers to recordings
- MusicBrainzSearcher: For fetching release details from MB API

This ensures consistent behavior between:
1. Regular song research flow (song_research.py → mb_release_importer.py)
2. Orphan recording import (this module)
"""

from flask import Blueprint, render_template, request, jsonify
import logging

from db_utils import get_db_connection
from mb_release_importer import MBReleaseImporter
from mb_performer_importer import PerformerImporter
from mb_utils import MusicBrainzSearcher

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/orphans')
def orphans_list():
    """List songs with orphan recordings for review"""
    with get_db_connection() as db:
        with db.cursor() as cur:
            # Get songs that have orphan recordings
            cur.execute("""
                SELECT
                    s.id,
                    s.title,
                    s.composer,
                    s.musicbrainz_id,
                    COUNT(o.id) as orphan_count,
                    COUNT(CASE WHEN o.status = 'pending' THEN 1 END) as pending_count,
                    COUNT(CASE WHEN o.status = 'approved' THEN 1 END) as approved_count,
                    COUNT(CASE WHEN o.status = 'rejected' THEN 1 END) as rejected_count,
                    COUNT(CASE WHEN o.spotify_track_id IS NOT NULL THEN 1 END) as with_spotify
                FROM songs s
                JOIN orphan_recordings o ON s.id = o.song_id
                GROUP BY s.id, s.title, s.composer, s.musicbrainz_id
                ORDER BY s.title
            """)
            songs = [dict(row) for row in cur.fetchall()]

    return render_template('admin/orphans_list.html', songs=songs)


@admin_bp.route('/orphans/<song_id>')
def orphans_review(song_id):
    """Review orphan recordings for a specific song"""
    with get_db_connection() as db:
        with db.cursor() as cur:
            # Get song info
            cur.execute("""
                SELECT id, title, composer, musicbrainz_id
                FROM songs WHERE id = %s
            """, (song_id,))
            song = cur.fetchone()

            if not song:
                return "Song not found", 404

            song = dict(song)

            # Get orphan recordings for this song
            cur.execute("""
                SELECT
                    id,
                    mb_recording_id,
                    mb_recording_title,
                    mb_artist_credit,
                    mb_first_release_date,
                    mb_length_ms,
                    mb_disambiguation,
                    mb_releases,
                    issue_type,
                    spotify_track_id,
                    spotify_track_name,
                    spotify_artist_name,
                    spotify_album_name,
                    spotify_preview_url,
                    spotify_external_url,
                    spotify_album_art_url,
                    spotify_match_confidence,
                    spotify_match_score,
                    spotify_matched_mb_release_id,
                    status,
                    review_notes,
                    reviewed_at,
                    imported_recording_id
                FROM orphan_recordings
                WHERE song_id = %s
                ORDER BY
                    CASE status
                        WHEN 'pending' THEN 1
                        WHEN 'approved' THEN 2
                        WHEN 'imported' THEN 3
                        WHEN 'rejected' THEN 4
                    END,
                    CASE spotify_match_confidence
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 3
                        ELSE 4
                    END,
                    mb_artist_credit
            """, (song_id,))
            orphans = [dict(row) for row in cur.fetchall()]

    return render_template('admin/orphans_review.html', song=song, orphans=orphans)


@admin_bp.route('/orphans/<orphan_id>/status', methods=['POST'])
def update_orphan_status(orphan_id):
    """Update the status of an orphan recording"""
    data = request.get_json()
    new_status = data.get('status')
    notes = data.get('notes', '')

    if new_status not in ['pending', 'approved', 'rejected']:
        return jsonify({'error': 'Invalid status'}), 400

    try:
        with get_db_connection() as db:
            with db.cursor() as cur:
                cur.execute("""
                    UPDATE orphan_recordings
                    SET status = %s,
                        review_notes = %s,
                        reviewed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id, status
                """, (new_status, notes, orphan_id))
                result = cur.fetchone()
                db.commit()

        if result:
            return jsonify({'success': True, 'id': str(result['id']), 'status': result['status']})
        else:
            return jsonify({'error': 'Orphan not found'}), 404

    except Exception as e:
        logger.error(f"Error updating orphan status: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/orphans/<song_id>/bulk-reject', methods=['POST'])
def bulk_reject_by_artist(song_id):
    """Bulk reject all pending orphans by a specific artist"""
    data = request.get_json()
    artist_credit = data.get('artist_credit')
    notes = data.get('notes', 'Bulk rejected')

    if not artist_credit:
        return jsonify({'error': 'artist_credit is required'}), 400

    try:
        with get_db_connection() as db:
            with db.cursor() as cur:
                cur.execute("""
                    UPDATE orphan_recordings
                    SET status = 'rejected',
                        review_notes = %s,
                        reviewed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE song_id = %s
                      AND mb_artist_credit = %s
                      AND status = 'pending'
                    RETURNING id
                """, (notes, song_id, artist_credit))
                results = cur.fetchall()
                db.commit()

        return jsonify({
            'success': True,
            'rejected_count': len(results)
        })

    except Exception as e:
        logger.error(f"Error bulk rejecting orphans: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/orphans/<song_id>')
def api_orphans_for_song(song_id):
    """API endpoint to get orphan recordings for a song"""
    with get_db_connection() as db:
        with db.cursor() as cur:
            cur.execute("""
                SELECT
                    id,
                    mb_recording_id,
                    mb_recording_title,
                    mb_artist_credit,
                    mb_first_release_date,
                    issue_type,
                    spotify_track_id,
                    spotify_track_name,
                    spotify_artist_name,
                    spotify_album_name,
                    spotify_preview_url,
                    spotify_external_url,
                    spotify_album_art_url,
                    spotify_match_confidence,
                    status,
                    review_notes
                FROM orphan_recordings
                WHERE song_id = %s
                ORDER BY mb_artist_credit
            """, (song_id,))
            orphans = [dict(row) for row in cur.fetchall()]

    # Convert UUIDs to strings for JSON
    for o in orphans:
        o['id'] = str(o['id'])

    return jsonify(orphans)


@admin_bp.route('/orphans/<song_id>/import', methods=['POST'])
def import_approved_orphans(song_id):
    """Import all approved orphan recordings for a song"""
    imported_count = 0
    errors = []

    try:
        with get_db_connection() as db:
            with db.cursor() as cur:
                # Get song info including work ID
                cur.execute("""
                    SELECT id, title, musicbrainz_id
                    FROM songs WHERE id = %s
                """, (song_id,))
                song = cur.fetchone()

                if not song:
                    return jsonify({'error': 'Song not found'}), 404

                # Get all approved orphans with Spotify data
                cur.execute("""
                    SELECT id, mb_recording_id, mb_recording_title, mb_artist_credit,
                           mb_artist_ids, mb_first_release_date, mb_releases,
                           spotify_track_id, spotify_track_name, spotify_album_name,
                           spotify_external_url, spotify_matched_mb_release_id
                    FROM orphan_recordings
                    WHERE song_id = %s AND status = 'approved'
                """, (song_id,))
                approved_orphans = [dict(row) for row in cur.fetchall()]

                if not approved_orphans:
                    return jsonify({'error': 'No approved orphans to import'}), 400

                for orphan in approved_orphans:
                    try:
                        # Pass db connection (not cursor) for MBReleaseImporter calls
                        recording_id = _import_single_orphan(db, song, orphan)
                        if recording_id:
                            imported_count += 1
                    except Exception as e:
                        logger.error(f"Error importing orphan {orphan['id']}: {e}")
                        errors.append(f"{orphan['mb_artist_credit']}: {str(e)}")

                db.commit()

        return jsonify({
            'success': True,
            'imported': imported_count,
            'errors': errors
        })

    except Exception as e:
        logger.error(f"Error in bulk import: {e}")
        return jsonify({'error': str(e)}), 500


def _import_single_orphan(db, song, orphan):
    """
    Import a single orphan recording into the recordings table.

    Uses shared code from MBReleaseImporter for release creation and CAA import
    to ensure consistent behavior with the main song research flow.

    Args:
        db: Database connection (not cursor) - needed for MBReleaseImporter calls
        song: Song dict with id, musicbrainz_id
        orphan: Orphan recording dict with all fields
    """
    song_id = song['id']
    work_id = song['musicbrainz_id']

    # Create cursor for this function's queries
    cur = db.cursor()

    # Parse year from release date
    recording_year = None
    release_date = orphan.get('mb_first_release_date')
    if release_date and len(release_date) >= 4:
        try:
            recording_year = int(release_date[:4])
        except ValueError:
            pass

    # Use Spotify album name if available, otherwise use artist credit as album title
    album_title = orphan.get('spotify_album_name') or orphan.get('mb_artist_credit', 'Unknown')

    # Check if recording already exists with this MB recording ID
    cur.execute("""
        SELECT id FROM recordings
        WHERE musicbrainz_id = %s AND song_id = %s
    """, (orphan['mb_recording_id'], song_id))

    existing = cur.fetchone()
    if existing:
        # Recording already exists, just update orphan status
        recording_id = existing['id']
        logger.info(f"Recording already exists: {orphan['mb_artist_credit']}")
    else:
        # Create new recording
        cur.execute("""
            INSERT INTO recordings (
                song_id, album_title, recording_year,
                mb_first_release_date, is_canonical,
                musicbrainz_id, source_mb_work_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            song_id,
            album_title,
            recording_year,
            release_date,
            False,  # Not canonical by default
            orphan['mb_recording_id'],
            work_id
        ))
        result = cur.fetchone()
        recording_id = result['id']
        logger.info(f"Created recording: {orphan['mb_artist_credit']} -> {recording_id}")

    # Link performers if we have MusicBrainz artist IDs
    artist_ids = orphan.get('mb_artist_ids') or []
    artist_names = (orphan.get('mb_artist_credit') or '').split(' / ')

    for i, mbid in enumerate(artist_ids):
        if not mbid:
            continue

        # Get performer name (if available)
        name = artist_names[i] if i < len(artist_names) else None

        # Find or create performer
        performer_id = _find_or_create_performer(cur, mbid, name)

        if performer_id:
            # Link performer to recording (as leader for first artist)
            role = 'leader' if i == 0 else 'sideman'
            cur.execute("""
                INSERT INTO recording_performers (recording_id, performer_id, role)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (recording_id, performer_id, role))

    # Link to release and add Spotify data if we have a matched release
    matched_release_id = orphan.get('spotify_matched_mb_release_id')
    spotify_track_id = orphan.get('spotify_track_id')

    if matched_release_id and spotify_track_id:
        # Find or create the release using full MBReleaseImporter flow
        # This ensures:
        # - Full release metadata from MusicBrainz API
        # - Cover Art Archive images imported
        # - Same code path as regular song research
        release_id, is_new = _find_or_create_release_with_caa(db, matched_release_id, orphan)

        if release_id:
            # Create recording_releases entry with Spotify data
            cur.execute("""
                INSERT INTO recording_releases (
                    recording_id, release_id, track_title, track_artist_credit,
                    spotify_track_id, spotify_track_url
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (recording_id, release_id) DO UPDATE
                SET spotify_track_id = EXCLUDED.spotify_track_id,
                    spotify_track_url = EXCLUDED.spotify_track_url
            """, (
                recording_id,
                release_id,
                orphan.get('mb_recording_title'),
                orphan.get('mb_artist_credit'),
                spotify_track_id,
                orphan.get('spotify_external_url')
            ))
            logger.info(f"Linked recording to release with Spotify: {spotify_track_id}"
                       f"{' (new release with CAA)' if is_new else ''}")

    # Update orphan status to imported
    cur.execute("""
        UPDATE orphan_recordings
        SET status = 'imported',
            imported_recording_id = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """, (recording_id, orphan['id']))

    # Close the cursor we created
    cur.close()

    return recording_id


def _find_or_create_performer(cur, mbid, name):
    """Find performer by MusicBrainz ID or create if not exists"""
    # Try to find by MBID
    cur.execute("""
        SELECT id FROM performers WHERE musicbrainz_id = %s
    """, (mbid,))
    result = cur.fetchone()
    if result:
        return result['id']

    # Try to find by name (case-insensitive)
    if name:
        cur.execute("""
            SELECT id FROM performers WHERE LOWER(name) = LOWER(%s)
        """, (name,))
        result = cur.fetchone()
        if result:
            # Update the existing performer with the MBID
            cur.execute("""
                UPDATE performers SET musicbrainz_id = %s WHERE id = %s
            """, (mbid, result['id']))
            return result['id']

        # Create new performer
        cur.execute("""
            INSERT INTO performers (name, musicbrainz_id)
            VALUES (%s, %s)
            RETURNING id
        """, (name, mbid))
        result = cur.fetchone()
        if result:
            logger.info(f"Created performer: {name}")
            return result['id']

    return None


def _find_or_create_release_with_caa(conn, mb_release_id: str, orphan: dict) -> tuple:
    """
    Find or create a release using the full MBReleaseImporter flow.

    This ensures:
    1. Release is created with full metadata from MusicBrainz API
    2. Cover art is fetched from Cover Art Archive
    3. Same code path as regular song research import

    Args:
        conn: Database connection
        mb_release_id: MusicBrainz release ID
        orphan: Orphan recording dict (for fallback artist credit)

    Returns:
        Tuple of (release_id, is_new) where is_new indicates if release was created
    """
    if not mb_release_id:
        return None, False

    with conn.cursor() as cur:
        # Try to find existing release
        cur.execute("""
            SELECT id FROM releases WHERE musicbrainz_release_id = %s
        """, (mb_release_id,))
        result = cur.fetchone()
        if result:
            return result['id'], False

    # Release doesn't exist - fetch full details from MusicBrainz and create
    # Use MBReleaseImporter which handles:
    # - Full release metadata parsing
    # - Lookup table management (formats, statuses, packaging)
    # - Cover Art Archive import

    mb_searcher = MusicBrainzSearcher()
    release_details = mb_searcher.get_release_details(mb_release_id)

    if not release_details:
        logger.warning(f"Could not fetch release details from MusicBrainz: {mb_release_id}")
        # Fall back to minimal release creation
        return _create_minimal_release(conn, mb_release_id, orphan), True

    # Use MBReleaseImporter for consistent release creation
    importer = MBReleaseImporter(dry_run=False, import_cover_art=True, logger=logger)

    # Load lookup table caches (formats, statuses, packaging)
    importer._load_lookup_caches(conn)

    # Parse release data using the same logic as regular import
    release_data = importer._parse_release_data(release_details)

    # Create the release
    release_id = importer._create_release(conn, release_data)

    if release_id:
        logger.info(f"Created release via MBReleaseImporter: {release_data.get('title')}")

        # Import cover art from Cover Art Archive
        # This is the same code path used during regular song research
        importer._import_cover_art_for_release(conn, release_id, mb_release_id)

    return release_id, True


def _create_minimal_release(conn, mb_release_id: str, orphan: dict):
    """
    Create a minimal release when MusicBrainz API fetch fails.

    This is a fallback for when we can't get full release details.
    The release can be enriched later via the CAA importer.
    """
    # Get basic info from the orphan's mb_releases data
    mb_releases = orphan.get('mb_releases') or []
    release_info = next(
        (r for r in mb_releases if r.get('id') == mb_release_id),
        {}
    )

    release_year = None
    release_date = release_info.get('date')
    if release_date and len(release_date) >= 4:
        try:
            release_year = int(release_date[:4])
        except ValueError:
            pass

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO releases (
                musicbrainz_release_id, title, artist_credit,
                release_year, country
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            mb_release_id,
            release_info.get('title'),
            orphan.get('mb_artist_credit'),
            release_year,
            release_info.get('country')
        ))
        result = cur.fetchone()
        if result:
            logger.info(f"Created minimal release (fallback): {release_info.get('title')}")
            return result['id']

    return None


@admin_bp.route('/orphans/<song_id>/existing-recordings')
def get_existing_recordings_for_song(song_id):
    """
    Get existing recordings for a song that an orphan could be linked to.

    Returns recordings with their releases and Spotify info to help identify
    if an orphan is the same performance as an existing recording.
    """
    with get_db_connection() as db:
        with db.cursor() as cur:
            # Get song info
            cur.execute("""
                SELECT id, title, musicbrainz_id FROM songs WHERE id = %s
            """, (song_id,))
            song = cur.fetchone()

            if not song:
                return jsonify({'error': 'Song not found'}), 404

            # Get existing recordings with their releases and Spotify data
            cur.execute("""
                SELECT
                    rec.id,
                    rec.musicbrainz_id as mb_recording_id,
                    rec.album_title,
                    rec.recording_year,
                    rec.mb_first_release_date,
                    p.name as leader_name,
                    p.id as leader_id,
                    -- Get releases for this recording
                    (
                        SELECT json_agg(json_build_object(
                            'release_id', rel.id,
                            'title', rel.title,
                            'year', rel.release_year,
                            'mb_release_id', rel.musicbrainz_release_id,
                            'spotify_album_url', rel.spotify_album_url,
                            'spotify_track_url', rr.spotify_track_url,
                            'album_art_small', COALESCE(
                                (SELECT ri.image_url_small FROM release_imagery ri
                                 WHERE ri.release_id = rel.id AND ri.type = 'front' LIMIT 1),
                                rel.album_art_small
                            )
                        ) ORDER BY rel.release_year)
                        FROM recording_releases rr
                        JOIN releases rel ON rr.release_id = rel.id
                        WHERE rr.recording_id = rec.id
                    ) as releases
                FROM recordings rec
                LEFT JOIN recording_performers rp ON rec.id = rp.recording_id AND rp.role = 'leader'
                LEFT JOIN performers p ON rp.performer_id = p.id
                WHERE rec.song_id = %s
                ORDER BY rec.recording_year, p.name
            """, (song_id,))

            recordings = []
            for row in cur.fetchall():
                rec = dict(row)
                # Parse releases JSON
                rec['releases'] = rec['releases'] or []
                # Add a flag for whether any release has Spotify
                rec['has_spotify'] = any(
                    r.get('spotify_album_url') or r.get('spotify_track_url')
                    for r in rec['releases']
                )
                recordings.append(rec)

            return jsonify({
                'song': dict(song),
                'recordings': recordings
            })


@admin_bp.route('/orphans/<orphan_id>/link-to-recording', methods=['POST'])
def link_orphan_to_existing_recording(orphan_id):
    """
    Link an orphan recording to an existing recording instead of creating a new one.

    This is used when the orphan is the same performance as an existing recording,
    just appearing on a different release (compilation, reissue, etc.).

    The orphan's MB release will be added as a new recording_releases entry
    for the existing recording.
    """
    data = request.get_json() or {}
    recording_id = data.get('recording_id')

    if not recording_id:
        return jsonify({'error': 'recording_id is required'}), 400

    try:
        with get_db_connection() as db:
            with db.cursor() as cur:
                # Get the orphan
                cur.execute("""
                    SELECT id, song_id, mb_recording_id, mb_recording_title, mb_artist_credit,
                           mb_releases, spotify_track_id, spotify_external_url,
                           spotify_matched_mb_release_id, status
                    FROM orphan_recordings
                    WHERE id = %s
                """, (orphan_id,))
                orphan = cur.fetchone()

                if not orphan:
                    return jsonify({'error': 'Orphan not found'}), 404

                orphan = dict(orphan)

                # Verify the recording exists and belongs to the same song
                cur.execute("""
                    SELECT id, song_id, musicbrainz_id FROM recordings WHERE id = %s
                """, (recording_id,))
                recording = cur.fetchone()

                if not recording:
                    return jsonify({'error': 'Recording not found'}), 404

                if str(recording['song_id']) != str(orphan['song_id']):
                    return jsonify({'error': 'Recording belongs to a different song'}), 400

                # Get the MB release to link (prefer Spotify-matched release, fall back to first release)
                mb_release_id = orphan.get('spotify_matched_mb_release_id')
                if not mb_release_id and orphan.get('mb_releases'):
                    mb_releases = orphan['mb_releases']
                    if mb_releases and len(mb_releases) > 0:
                        mb_release_id = mb_releases[0].get('id')

                if not mb_release_id:
                    return jsonify({'error': 'No MB release found for orphan'}), 400

                # Find or create the release
                release_id, is_new = _find_or_create_release_with_caa(db, mb_release_id, orphan)

                if not release_id:
                    return jsonify({'error': 'Could not find or create release'}), 500

                # Create recording_releases entry linking existing recording to this release
                cur.execute("""
                    INSERT INTO recording_releases (
                        recording_id, release_id, track_title, track_artist_credit,
                        spotify_track_id, spotify_track_url
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (recording_id, release_id) DO UPDATE
                    SET spotify_track_id = COALESCE(EXCLUDED.spotify_track_id, recording_releases.spotify_track_id),
                        spotify_track_url = COALESCE(EXCLUDED.spotify_track_url, recording_releases.spotify_track_url)
                    RETURNING id
                """, (
                    recording_id,
                    release_id,
                    orphan.get('mb_recording_title'),
                    orphan.get('mb_artist_credit'),
                    orphan.get('spotify_track_id'),
                    orphan.get('spotify_external_url')
                ))
                rr_result = cur.fetchone()

                # Update orphan status to 'linked' (a new status) or 'imported'
                cur.execute("""
                    UPDATE orphan_recordings
                    SET status = 'linked',
                        imported_recording_id = %s,
                        imported_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP,
                        review_notes = COALESCE(review_notes, '') || ' Linked to existing recording.'
                    WHERE id = %s
                """, (recording_id, orphan_id))

                db.commit()

                logger.info(f"Linked orphan {orphan_id} to existing recording {recording_id} via release {release_id}")

                return jsonify({
                    'success': True,
                    'recording_id': str(recording_id),
                    'release_id': str(release_id),
                    'release_is_new': is_new,
                    'recording_release_id': str(rr_result['id']) if rr_result else None
                })

    except Exception as e:
        logger.error(f"Error linking orphan to recording: {e}")
        return jsonify({'error': str(e)}), 500
