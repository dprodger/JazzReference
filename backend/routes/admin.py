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
    include_spotify = data.get('include_spotify')  # True/False/None

    if new_status not in ['pending', 'approved', 'rejected']:
        return jsonify({'error': 'Invalid status'}), 400

    try:
        with get_db_connection() as db:
            with db.cursor() as cur:
                # If approving and explicitly NOT including Spotify, clear the Spotify fields
                # so the import logic won't use them
                if new_status == 'approved' and include_spotify is False:
                    cur.execute("""
                        UPDATE orphan_recordings
                        SET status = %s,
                            review_notes = %s,
                            reviewed_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP,
                            spotify_track_id = NULL,
                            spotify_external_url = NULL,
                            spotify_matched_mb_release_id = NULL
                        WHERE id = %s
                        RETURNING id, status
                    """, (new_status, notes or 'Approved without Spotify link', orphan_id))
                else:
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


@admin_bp.route('/orphans/<song_id>/json')
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

    # Link to release - always create a release from MB data, with Spotify if available
    matched_release_id = orphan.get('spotify_matched_mb_release_id')
    spotify_track_id = orphan.get('spotify_track_id')

    # Determine which MB release to use:
    # 1. If we have a Spotify-matched release, use that
    # 2. Otherwise, use the first release from mb_releases
    mb_release_id = matched_release_id
    if not mb_release_id and orphan.get('mb_releases'):
        mb_releases = orphan['mb_releases']
        if mb_releases and len(mb_releases) > 0:
            mb_release_id = mb_releases[0].get('id')

    if mb_release_id:
        # Find or create the release using full MBReleaseImporter flow
        # This ensures:
        # - Full release metadata from MusicBrainz API
        # - Cover Art Archive images imported
        # - Same code path as regular song research
        release_id, is_new = _find_or_create_release_with_caa(db, mb_release_id, orphan)

        if release_id:
            # Create recording_releases entry (with Spotify track ID if available)
            cur.execute("""
                INSERT INTO recording_releases (
                    recording_id, release_id, track_title, track_artist_credit,
                    spotify_track_id
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (recording_id, release_id) DO UPDATE
                SET spotify_track_id = COALESCE(EXCLUDED.spotify_track_id, recording_releases.spotify_track_id)
            """, (
                recording_id,
                release_id,
                orphan.get('mb_recording_title'),
                orphan.get('mb_artist_credit'),
                spotify_track_id if spotify_track_id else None
            ))
            if spotify_track_id:
                logger.info(f"Linked recording to release with Spotify: {spotify_track_id}"
                           f"{' (new release with CAA)' if is_new else ''}")
            else:
                logger.info(f"Linked recording to release (no Spotify): {mb_release_id}"
                           f"{' (new release with CAA)' if is_new else ''}")

            # Set default_release_id if recording doesn't have one
            cur.execute("""
                UPDATE recordings
                SET default_release_id = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                  AND default_release_id IS NULL
            """, (release_id, recording_id))

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
                            'spotify_album_id', rel.spotify_album_id,
                            'spotify_album_url', CASE WHEN rel.spotify_album_id IS NOT NULL
                                THEN 'https://open.spotify.com/album/' || rel.spotify_album_id END,
                            'spotify_track_id', rr.spotify_track_id,
                            'spotify_track_url', CASE WHEN rr.spotify_track_id IS NOT NULL
                                THEN 'https://open.spotify.com/track/' || rr.spotify_track_id END,
                            'album_art_small', COALESCE(
                                (SELECT ri.image_url_small FROM release_imagery ri
                                 WHERE ri.release_id = rel.id AND ri.type = 'Front' LIMIT 1),
                                rel.cover_art_small
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
                ORDER BY rec.recording_year, COALESCE(p.sort_name, p.name)
            """, (song_id,))

            recordings = []
            for row in cur.fetchall():
                rec = dict(row)
                # Parse releases JSON
                rec['releases'] = rec['releases'] or []
                # Add a flag for whether any release has Spotify
                rec['has_spotify'] = any(
                    r.get('spotify_album_id') or r.get('spotify_track_id')
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
                        spotify_track_id
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (recording_id, release_id) DO UPDATE
                    SET spotify_track_id = COALESCE(EXCLUDED.spotify_track_id, recording_releases.spotify_track_id)
                    RETURNING id
                """, (
                    recording_id,
                    release_id,
                    orphan.get('mb_recording_title'),
                    orphan.get('mb_artist_credit'),
                    orphan.get('spotify_track_id')
                ))
                rr_result = cur.fetchone()

                # Set default_release_id if recording doesn't have one, or if this release
                # has Spotify data and the current default doesn't
                has_spotify = bool(orphan.get('spotify_track_id'))
                cur.execute("""
                    UPDATE recordings
                    SET default_release_id = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                      AND (
                          default_release_id IS NULL
                          OR (%s AND NOT EXISTS (
                              SELECT 1 FROM releases rel
                              WHERE rel.id = default_release_id
                                AND rel.spotify_album_id IS NOT NULL
                          ))
                      )
                """, (release_id, recording_id, has_spotify))

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


# =============================================================================
# AUTHORITY RECOMMENDATIONS REVIEWER
# =============================================================================

@admin_bp.route('/recommendations')
def recommendations_list():
    """
    List songs with authority recommendations and their completion status.
    Shows which songs have unmatched recommendations that need attention.
    """
    with get_db_connection() as db:
        with db.cursor() as cur:
            cur.execute("""
                SELECT
                    s.id,
                    s.title,
                    s.composer,
                    s.musicbrainz_id,
                    COUNT(*) AS total_recs,
                    COUNT(sar.recording_id) AS matched_recs,
                    ROUND(COUNT(sar.recording_id)::decimal / COUNT(*) * 100, 1) AS perc_complete,
                    COUNT(*) FILTER (WHERE sar.artist_name IS NULL OR sar.artist_name = '') AS missing_artist,
                    COUNT(*) FILTER (WHERE sar.album_title IS NULL OR sar.album_title = '') AS missing_album,
                    array_agg(DISTINCT sar.source) AS sources
                FROM songs s
                JOIN song_authority_recommendations sar ON s.id = sar.song_id
                GROUP BY s.id, s.title, s.composer, s.musicbrainz_id
                ORDER BY perc_complete ASC, total_recs DESC
            """)
            songs = [dict(row) for row in cur.fetchall()]

    return render_template('admin/recommendations_list.html', songs=songs)


@admin_bp.route('/recommendations/<song_id>')
def recommendations_review(song_id):
    """
    Review unmatched authority recommendations for a specific song.
    Shows detailed diagnostic information for each recommendation.
    """
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

            # Get all recommendations for this song
            cur.execute("""
                SELECT
                    sar.id,
                    sar.song_id,
                    sar.recording_id,
                    sar.source,
                    sar.recommendation_text,
                    sar.source_url,
                    sar.artist_name,
                    sar.album_title,
                    sar.recording_year,
                    sar.itunes_album_id,
                    sar.itunes_track_id,
                    sar.created_at,
                    -- If matched, get recording info
                    r.album_title AS matched_album,
                    p.name AS matched_performer
                FROM song_authority_recommendations sar
                LEFT JOIN recordings r ON sar.recording_id = r.id
                LEFT JOIN recording_performers rp ON r.id = rp.recording_id AND rp.role = 'leader'
                LEFT JOIN performers p ON rp.performer_id = p.id
                WHERE sar.song_id = %s
                ORDER BY
                    CASE WHEN sar.recording_id IS NULL THEN 0 ELSE 1 END,
                    sar.source,
                    sar.artist_name
            """, (song_id,))
            recommendations = [dict(row) for row in cur.fetchall()]

            # Calculate stats
            total = len(recommendations)
            matched = sum(1 for r in recommendations if r['recording_id'])
            unmatched = total - matched
            missing_artist = sum(1 for r in recommendations
                               if not r['recording_id'] and (not r['artist_name'] or r['artist_name'].strip() == ''))
            missing_album = sum(1 for r in recommendations
                              if not r['recording_id'] and (not r['album_title'] or r['album_title'].strip() == ''))

            stats = {
                'total': total,
                'matched': matched,
                'unmatched': unmatched,
                'missing_artist': missing_artist,
                'missing_album': missing_album,
                'perc_complete': round(matched / total * 100, 1) if total > 0 else 0
            }

    return render_template('admin/recommendations_review.html',
                          song=song,
                          recommendations=recommendations,
                          stats=stats)


@admin_bp.route('/recommendations/<song_id>/potential-matches/<rec_id>')
def get_potential_matches(song_id, rec_id):
    """
    Find potential release matches for an unmatched recommendation.
    Searches releases by artist name and album title similarity.
    """
    with get_db_connection() as db:
        with db.cursor() as cur:
            # Get the recommendation
            cur.execute("""
                SELECT id, artist_name, album_title, recording_year
                FROM song_authority_recommendations
                WHERE id = %s AND song_id = %s
            """, (rec_id, song_id))
            rec = cur.fetchone()

            if not rec:
                return jsonify({'error': 'Recommendation not found'}), 404

            rec = dict(rec)
            artist_name = rec.get('artist_name') or ''
            album_title = rec.get('album_title') or ''

            # Search for potential matches in releases
            # Using ILIKE for case-insensitive partial matching
            cur.execute("""
                SELECT DISTINCT
                    rel.id AS release_id,
                    rel.title AS release_title,
                    rel.artist_credit,
                    rel.release_year,
                    rel.musicbrainz_release_id,
                    rel.spotify_album_id,
                    COALESCE(
                        (SELECT ri.image_url_small FROM release_imagery ri
                         WHERE ri.release_id = rel.id AND ri.type = 'Front' LIMIT 1),
                        rel.cover_art_small
                    ) AS cover_art,
                    r.id AS recording_id,
                    r.album_title AS recording_album
                FROM releases rel
                LEFT JOIN recording_releases rr ON rel.id = rr.release_id
                LEFT JOIN recordings r ON rr.recording_id = r.id AND r.song_id = %s
                WHERE (
                    rel.artist_credit ILIKE %s
                    OR rel.title ILIKE %s
                )
                ORDER BY
                    CASE WHEN r.id IS NOT NULL THEN 0 ELSE 1 END,
                    rel.release_year DESC
                LIMIT 20
            """, (
                song_id,
                f'%{artist_name}%' if artist_name else '%',
                f'%{album_title}%' if album_title else '%'
            ))

            matches = [dict(row) for row in cur.fetchall()]

            # Convert UUIDs to strings
            for m in matches:
                if m.get('release_id'):
                    m['release_id'] = str(m['release_id'])
                if m.get('recording_id'):
                    m['recording_id'] = str(m['recording_id'])

    return jsonify({
        'recommendation': {
            'id': str(rec['id']),
            'artist_name': rec['artist_name'],
            'album_title': rec['album_title'],
            'recording_year': rec['recording_year']
        },
        'matches': matches
    })


@admin_bp.route('/recommendations/<rec_id>/link', methods=['POST'])
def link_recommendation_to_recording(rec_id):
    """
    Manually link an authority recommendation to a recording.
    """
    data = request.get_json() or {}
    recording_id = data.get('recording_id')

    if not recording_id:
        return jsonify({'error': 'recording_id is required'}), 400

    try:
        with get_db_connection() as db:
            with db.cursor() as cur:
                cur.execute("""
                    UPDATE song_authority_recommendations
                    SET recording_id = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id, recording_id
                """, (recording_id, rec_id))
                result = cur.fetchone()
                db.commit()

                if not result:
                    return jsonify({'error': 'Recommendation not found'}), 404

                return jsonify({
                    'success': True,
                    'recommendation_id': str(result['id']),
                    'recording_id': str(result['recording_id'])
                })

    except Exception as e:
        logger.error(f"Error linking recommendation: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/recommendations/<rec_id>/unlink', methods=['POST'])
def unlink_recommendation(rec_id):
    """
    Remove the recording link from an authority recommendation.
    """
    try:
        with get_db_connection() as db:
            with db.cursor() as cur:
                cur.execute("""
                    UPDATE song_authority_recommendations
                    SET recording_id = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id
                """, (rec_id,))
                result = cur.fetchone()
                db.commit()

                if not result:
                    return jsonify({'error': 'Recommendation not found'}), 404

                return jsonify({
                    'success': True,
                    'recommendation_id': str(result['id'])
                })

    except Exception as e:
        logger.error(f"Error unlinking recommendation: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/recommendations/<song_id>/diagnose', methods=['POST'])
def diagnose_mb_recording(song_id):
    """
    Diagnose why a MusicBrainz recording isn't matching.

    Takes a MusicBrainz recording URL and returns:
    - Is the recording linked to this song's Work in MusicBrainz?
    - Do we have this recording in our database?
    - Do we have its releases?
    - Where does the matching logic fail?
    """
    import re
    import requests
    from rapidfuzz import fuzz

    data = request.get_json() or {}
    mb_url = data.get('url', '').strip()
    rec_id = data.get('recommendation_id')  # Optional: to compare against specific rec

    # Parse recording ID from URL
    # Supports: https://musicbrainz.org/recording/UUID or just UUID
    mb_recording_id = None
    uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'

    match = re.search(uuid_pattern, mb_url, re.IGNORECASE)
    if match:
        mb_recording_id = match.group(0).lower()
    else:
        return jsonify({'error': 'Could not parse MusicBrainz recording ID from URL'}), 400

    diagnosis = {
        'mb_recording_id': mb_recording_id,
        'mb_url': f'https://musicbrainz.org/recording/{mb_recording_id}',
        'checks': [],
        'recommendation': None,
        'mb_data': None,
        'our_data': None,
        'issues': [],
        'suggestions': []
    }

    try:
        with get_db_connection() as db:
            with db.cursor() as cur:
                # Get song info including Work IDs (primary and secondary)
                cur.execute("""
                    SELECT id, title, musicbrainz_id, second_mb_id
                    FROM songs WHERE id = %s
                """, (song_id,))
                song = cur.fetchone()

                if not song:
                    return jsonify({'error': 'Song not found'}), 404

                song = dict(song)
                # Collect all valid work IDs for this song
                our_work_ids = [song['musicbrainz_id']] if song['musicbrainz_id'] else []
                if song.get('second_mb_id'):
                    our_work_ids.append(song['second_mb_id'])

                diagnosis['song'] = {
                    'id': str(song['id']),
                    'title': song['title'],
                    'work_id': song['musicbrainz_id'],
                    'second_work_id': song.get('second_mb_id'),
                    'all_work_ids': our_work_ids
                }

                # Get the recommendation if provided
                if rec_id:
                    cur.execute("""
                        SELECT id, artist_name, album_title, recording_year, source
                        FROM song_authority_recommendations
                        WHERE id = %s
                    """, (rec_id,))
                    rec = cur.fetchone()
                    if rec:
                        diagnosis['recommendation'] = dict(rec)
                        diagnosis['recommendation']['id'] = str(rec['id'])

                # ===== CHECK 1: Fetch from MusicBrainz =====
                mb_session = requests.Session()
                mb_session.headers.update({
                    'User-Agent': 'JazzReferenceAdmin/1.0 (diagnostic tool)'
                })

                # Fetch recording with work-rels and releases
                mb_response = mb_session.get(
                    f'https://musicbrainz.org/ws/2/recording/{mb_recording_id}',
                    params={
                        'inc': 'releases+artist-credits+work-rels',
                        'fmt': 'json'
                    },
                    timeout=15
                )

                if mb_response.status_code == 404:
                    diagnosis['checks'].append({
                        'name': 'MB Recording Exists',
                        'passed': False,
                        'detail': 'Recording not found in MusicBrainz'
                    })
                    diagnosis['issues'].append('Recording does not exist in MusicBrainz')
                    return jsonify(diagnosis)

                if mb_response.status_code != 200:
                    diagnosis['checks'].append({
                        'name': 'MB API Call',
                        'passed': False,
                        'detail': f'MusicBrainz API error: {mb_response.status_code}'
                    })
                    return jsonify(diagnosis)

                mb_data = mb_response.json()
                diagnosis['checks'].append({
                    'name': 'MB Recording Exists',
                    'passed': True,
                    'detail': f"Found: {mb_data.get('title')}"
                })

                # Extract MB data
                mb_artist_credit = ' / '.join([
                    ac.get('name', ac.get('artist', {}).get('name', ''))
                    for ac in mb_data.get('artist-credit', [])
                ])
                mb_releases = mb_data.get('releases', [])

                diagnosis['mb_data'] = {
                    'title': mb_data.get('title'),
                    'artist_credit': mb_artist_credit,
                    'releases': [
                        {
                            'id': r.get('id'),
                            'title': r.get('title'),
                            'date': r.get('date'),
                            'country': r.get('country')
                        }
                        for r in mb_releases[:10]  # Limit to first 10
                    ],
                    'total_releases': len(mb_releases)
                }

                # ===== CHECK 2: Is it linked to the Work? =====
                work_relations = mb_data.get('relations', [])
                work_links = [
                    rel for rel in work_relations
                    if rel.get('type') == 'performance' and rel.get('work')
                ]

                linked_to_our_work = False
                matched_work_title = None
                linked_works = []
                for rel in work_links:
                    work = rel.get('work', {})
                    work_id = work.get('id')
                    work_title = work.get('title')
                    # Check against both primary and secondary work IDs
                    is_ours = work_id in our_work_ids
                    linked_works.append({
                        'id': work_id,
                        'title': work_title,
                        'is_ours': is_ours
                    })
                    if is_ours:
                        linked_to_our_work = True
                        matched_work_title = work_title

                diagnosis['mb_data']['linked_works'] = linked_works

                if linked_to_our_work:
                    # Show which work ID matched (primary or secondary)
                    work_note = ""
                    if matched_work_title and matched_work_title.lower() != song['title'].lower():
                        work_note = f" (via alternate title: {matched_work_title})"
                    diagnosis['checks'].append({
                        'name': 'Linked to Work',
                        'passed': True,
                        'detail': f"Recording IS linked to '{song['title']}' in MusicBrainz{work_note}"
                    })
                elif linked_works:
                    diagnosis['checks'].append({
                        'name': 'Linked to Work',
                        'passed': False,
                        'detail': f"Recording is linked to OTHER works: {', '.join([w['title'] for w in linked_works])}"
                    })
                    diagnosis['issues'].append(f"Recording is linked to wrong Work(s) in MusicBrainz: {', '.join([w['title'] for w in linked_works])}")
                    diagnosis['suggestions'].append("Edit MusicBrainz to add a 'performance of' relationship to the correct Work")
                else:
                    diagnosis['checks'].append({
                        'name': 'Linked to Work',
                        'passed': False,
                        'detail': "Recording has NO work relationships in MusicBrainz"
                    })
                    diagnosis['issues'].append("Recording is not linked to any Work in MusicBrainz")
                    diagnosis['suggestions'].append("Edit MusicBrainz to add a 'performance of' relationship to this Work")

                # ===== CHECK 3: Do we have this recording? =====
                cur.execute("""
                    SELECT r.id, r.album_title, r.recording_year, r.musicbrainz_id,
                           p.name as leader_name
                    FROM recordings r
                    LEFT JOIN recording_performers rp ON r.id = rp.recording_id AND rp.role = 'leader'
                    LEFT JOIN performers p ON rp.performer_id = p.id
                    WHERE r.musicbrainz_id = %s
                """, (mb_recording_id,))
                our_recording = cur.fetchone()

                if our_recording:
                    our_recording = dict(our_recording)
                    diagnosis['checks'].append({
                        'name': 'In Our Database',
                        'passed': True,
                        'detail': f"We have this recording: {our_recording['leader_name'] or 'Unknown'} - {our_recording['album_title']}"
                    })
                    diagnosis['our_data'] = {
                        'recording_id': str(our_recording['id']),
                        'album_title': our_recording['album_title'],
                        'recording_year': our_recording['recording_year'],
                        'leader_name': our_recording['leader_name']
                    }
                else:
                    diagnosis['checks'].append({
                        'name': 'In Our Database',
                        'passed': False,
                        'detail': "We do NOT have this recording in our database"
                    })
                    if linked_to_our_work:
                        diagnosis['issues'].append("Recording is linked to Work but we haven't imported it")
                        diagnosis['suggestions'].append("Re-run the MusicBrainz import for this song to pick up this recording")
                    else:
                        diagnosis['issues'].append("Recording not imported (not linked to Work in MB)")

                # ===== CHECK 4: Do we have the releases? =====
                if mb_releases:
                    mb_release_ids = [r.get('id') for r in mb_releases]
                    placeholders = ','.join(['%s'] * len(mb_release_ids))
                    cur.execute(f"""
                        SELECT musicbrainz_release_id, title, artist_credit
                        FROM releases
                        WHERE musicbrainz_release_id IN ({placeholders})
                    """, mb_release_ids)
                    our_releases = {r['musicbrainz_release_id']: dict(r) for r in cur.fetchall()}

                    matched_releases = []
                    missing_releases = []
                    for mb_rel in mb_releases[:5]:  # Check first 5
                        if mb_rel.get('id') in our_releases:
                            matched_releases.append(mb_rel.get('title'))
                        else:
                            missing_releases.append({
                                'id': mb_rel.get('id'),
                                'title': mb_rel.get('title')
                            })

                    if matched_releases:
                        diagnosis['checks'].append({
                            'name': 'Have Releases',
                            'passed': True,
                            'detail': f"We have {len(matched_releases)} of the releases: {', '.join(matched_releases[:3])}"
                        })
                    else:
                        diagnosis['checks'].append({
                            'name': 'Have Releases',
                            'passed': False,
                            'detail': "We don't have any of this recording's releases"
                        })
                        diagnosis['issues'].append("None of the recording's releases are in our database")

                    diagnosis['our_data'] = diagnosis.get('our_data') or {}
                    diagnosis['our_data']['matched_releases'] = matched_releases
                    diagnosis['our_data']['missing_releases'] = missing_releases[:5]

                # ===== CHECK 5: Compare with recommendation =====
                if diagnosis.get('recommendation'):
                    rec = diagnosis['recommendation']
                    rec_artist = rec.get('artist_name') or ''
                    rec_album = rec.get('album_title') or ''

                    # Artist comparison
                    artist_score = fuzz.ratio(rec_artist.lower(), mb_artist_credit.lower())
                    artist_partial = fuzz.partial_ratio(rec_artist.lower(), mb_artist_credit.lower())

                    diagnosis['checks'].append({
                        'name': 'Artist Match',
                        'passed': artist_score >= 80 or artist_partial >= 90,
                        'detail': f"Rec artist: '{rec_artist}' vs MB: '{mb_artist_credit}' (score: {artist_score}%, partial: {artist_partial}%)"
                    })

                    if artist_score < 80 and artist_partial < 90:
                        diagnosis['issues'].append(f"Artist name mismatch: '{rec_artist}' vs '{mb_artist_credit}'")
                        diagnosis['suggestions'].append("Check if the matcher needs to handle this artist name variation")

                    # Album comparison (against all MB releases)
                    best_album_score = 0
                    best_album_match = None
                    for mb_rel in mb_releases:
                        rel_title = mb_rel.get('title', '')
                        score = fuzz.ratio(rec_album.lower(), rel_title.lower())
                        if score > best_album_score:
                            best_album_score = score
                            best_album_match = rel_title

                    diagnosis['checks'].append({
                        'name': 'Album Match',
                        'passed': best_album_score >= 80,
                        'detail': f"Rec album: '{rec_album}' vs best MB match: '{best_album_match}' (score: {best_album_score}%)"
                    })

                    if best_album_score < 80:
                        diagnosis['issues'].append(f"Album title mismatch: '{rec_album}' doesn't match any MB release (best: {best_album_score}%)")
                        diagnosis['suggestions'].append("The recommendation's album title may be different from MB release titles")

                # ===== Summary =====
                if not diagnosis['issues']:
                    if our_recording:
                        diagnosis['summary'] = "This recording exists in our database. The matcher may need to be re-run or there's a logic issue."
                    else:
                        diagnosis['summary'] = "All checks passed but recording not imported. Try re-importing from MusicBrainz."
                else:
                    diagnosis['summary'] = f"Found {len(diagnosis['issues'])} issue(s) preventing the match."

                return jsonify(diagnosis)

    except Exception as e:
        logger.error(f"Error in diagnosis: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
