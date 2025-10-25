#!/usr/bin/env python3
"""
Shared utilities for importing performer and instrument data from MusicBrainz
"""

import json
import logging
import time
import requests
from db_utils import get_db_connection

logger = logging.getLogger(__name__)

class PerformerImporter:
    """Handles importing performers and instruments from MusicBrainz data"""
    
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'JazzReference/1.0 (https://github.com/yourusername/jazzreference)',
            'Accept': 'application/json'
        })
        self.stats = {
            'performers_created': 0,
            'instruments_created': 0,
            'performer_links_created': 0
        }
    
    def fetch_release_credits(self, release_id):
        """
        Fetch detailed credits from a release
        
        Args:
            release_id: MusicBrainz release MBID
            
        Returns:
            Release data dict or None if error
        """
        url = f"https://musicbrainz.org/ws/2/release/{release_id}"
        params = {
            'inc': 'artist-credits+recordings+artist-rels',
            'fmt': 'json'
        }
        
        try:
            time.sleep(1.0)  # Rate limiting
            logger.debug(f"      Fetching release credits: {release_id}")
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"      Error fetching release credits: {e}")
            return None
    
    def parse_release_artist_credits(self, release_data, target_recording_id=None):
        """
        Parse artist credits from a release, optionally for a specific recording
        
        Args:
            release_data: MusicBrainz release data
            target_recording_id: If provided, only get credits for this recording
            
        Returns:
            List of dicts with keys: name, mbid, instruments, role
        """
        performers = []
        
        # Check release-level relationships first
        relations = release_data.get('relations', [])
        if relations:
            logger.debug(f"      Checking {len(relations)} release-level relations")
            release_performers = self.parse_artist_relationships(relations)
            if release_performers:
                logger.debug(f"      Found {len(release_performers)} performers from release relationships")
                return release_performers
        
        # Check track-level credits
        media = release_data.get('media', [])
        for medium in media:
            tracks = medium.get('tracks', [])
            for track in tracks:
                recording = track.get('recording', {})
                recording_id = recording.get('id')
                
                # If we're looking for a specific recording, skip others
                if target_recording_id and recording_id != target_recording_id:
                    continue
                
                # Check track artist credits
                track_artist_credits = track.get('artist-credit', [])
                if track_artist_credits:
                    logger.debug(f"      Found artist credits on track: {track.get('title')}")
                    # Note: track credits usually don't have instruments, but let's check
                    for credit in track_artist_credits:
                        if 'artist' in credit:
                            artist = credit['artist']
                            performers.append({
                                'name': artist.get('name'),
                                'mbid': artist.get('id'),
                                'instruments': [],  # Track credits typically don't have instruments
                                'role': 'performer'
                            })
                
                # Check recording relationships on this track
                recording_relations = recording.get('relations', [])
                if recording_relations:
                    logger.debug(f"      Checking {len(recording_relations)} recording relations on track")
                    track_performers = self.parse_artist_relationships(recording_relations)
                    if track_performers:
                        performers.extend(track_performers)
                
                # If we were looking for a specific recording and found it, we're done
                if target_recording_id and recording_id == target_recording_id:
                    break
        
        return performers
    
    def parse_artist_credits(self, artist_credits):
        """
        Parse MusicBrainz artist credits into a list of artists
        
        Args:
            artist_credits: List of artist credit dicts from MusicBrainz
            
        Returns:
            List of dicts with keys: name, mbid, sort_name
        """
        if not artist_credits:
            return []
        
        artists = []
        for credit in artist_credits:
            if 'artist' in credit:
                artist = credit['artist']
                artists.append({
                    'name': artist.get('name'),
                    'mbid': artist.get('id'),
                    'sort_name': artist.get('sort-name')
                })
        
        return artists
    
    def parse_artist_relationships(self, relations):
        """
        Parse MusicBrainz artist relationships to extract performer and instrument information
        
        CRITICAL: MusicBrainz uses these relationship types:
        - 'instrument': Musicians playing instruments (attributes contain instrument names)
        - 'engineer': Recording engineers (no instruments)
        - 'producer': Producers (no instruments)
        - NOT 'performance' - that's for work->recording relationships
        
        Args:
            relations: List of relationship dicts from MusicBrainz
            
        Returns:
            List of dicts with keys: name, mbid, instruments (list), role
        """
        if not relations:
            logger.debug("      No relations found in MusicBrainz data")
            return []
        
        logger.debug(f"      Examining {len(relations)} relations from MusicBrainz")
        
        performers = []
        relation_types_seen = set()
        
        for relation in relations:
            rel_type = relation.get('type', 'unknown')
            target_type = relation.get('target-type', 'unknown')
            direction = relation.get('direction', 'unknown')
            
            relation_types_seen.add(rel_type)
            
            # Only process artist relationships (not work, url, etc.)
            if target_type != 'artist':
                continue
            
            # Skip if no artist data
            if 'artist' not in relation:
                continue
            
            artist = relation['artist']
            artist_name = artist.get('name')
            artist_mbid = artist.get('id')
            
            if not artist_name:
                continue
            
            # Extract instruments from attributes (for 'instrument' type)
            instruments = []
            role = rel_type  # Default role is the relationship type
            
            if rel_type == 'instrument':
                # For instrument relationships, attributes contain the actual instrument names
                attributes = relation.get('attributes', [])
                for attr in attributes:
                    # MusicBrainz instrument attributes are strings
                    if isinstance(attr, str):
                        instruments.append(attr)
                    elif isinstance(attr, dict) and 'name' in attr:
                        instruments.append(attr['name'])
                
                if not instruments:
                    logger.debug(f"      Warning: 'instrument' relation for {artist_name} has no instruments")
            
            elif rel_type in ['engineer', 'producer', 'vocal', 'mix', 'mastering']:
                # These are valid relationship types but don't have instrument attributes
                # They represent roles rather than instruments
                role = rel_type
            
            else:
                # Other relationship types - log for debugging
                logger.debug(f"      Found {rel_type} relationship for {artist_name} (not processing)")
                continue
            
            performers.append({
                'name': artist_name,
                'mbid': artist_mbid,
                'instruments': instruments,
                'role': role
            })
            
            logger.debug(f"      Added performer: {artist_name} - {role}" + 
                        (f" ({', '.join(instruments)})" if instruments else ""))
        
        if relation_types_seen:
            logger.debug(f"      Relation types seen: {', '.join(sorted(relation_types_seen))}")
        
        return performers
    
    def get_or_create_performer(self, conn, artist_name, artist_mbid=None):
        """
        Get existing performer or create new one
        
        Args:
            conn: Database connection
            artist_name: Performer name
            artist_mbid: MusicBrainz artist ID (optional)
            
        Returns:
            Performer ID or None if dry_run
        """
        with conn.cursor() as cur:
            # Try to find by MusicBrainz ID first
            if artist_mbid:
                cur.execute("""
                    SELECT id FROM performers
                    WHERE external_links->>'musicbrainz' = %s
                """, (artist_mbid,))
                result = cur.fetchone()
                
                if result:
                    logger.debug(f"Found existing performer by MBID: {artist_name}")
                    return result['id']
            
            # Try to find by name (case-insensitive)
            cur.execute("""
                SELECT id FROM performers
                WHERE name ILIKE %s
            """, (artist_name,))
            result = cur.fetchone()
            
            if result:
                logger.debug(f"Found existing performer: {artist_name}")
                return result['id']
            
            # Create new performer
            if self.dry_run:
                logger.info(f"[DRY RUN] Would create performer: {artist_name}")
                return None
            
            external_links = {}
            if artist_mbid:
                external_links['musicbrainz'] = artist_mbid
            
            cur.execute("""
                INSERT INTO performers (name, external_links)
                VALUES (%s, %s)
                RETURNING id
            """, (artist_name, json.dumps(external_links)))
            
            performer_id = cur.fetchone()['id']
            logger.info(f"Created new performer: {artist_name} (ID: {performer_id})")
            self.stats['performers_created'] += 1
            
            return performer_id
    
    def get_or_create_instrument(self, conn, instrument_name):
        """
        Get existing instrument or create new one
        
        Args:
            conn: Database connection
            instrument_name: Instrument name
            
        Returns:
            Instrument ID or None if dry_run
        """
        with conn.cursor() as cur:
            # Try to find by name (case-insensitive)
            cur.execute("""
                SELECT id FROM instruments
                WHERE name ILIKE %s
            """, (instrument_name,))
            result = cur.fetchone()
            
            if result:
                return result['id']
            
            # Create new instrument
            if self.dry_run:
                logger.debug(f"[DRY RUN] Would create instrument: {instrument_name}")
                return None
            
            cur.execute("""
                INSERT INTO instruments (name)
                VALUES (%s)
                RETURNING id
            """, (instrument_name,))
            
            instrument_id = cur.fetchone()['id']
            logger.debug(f"Created new instrument: {instrument_name} (ID: {instrument_id})")
            self.stats['instruments_created'] += 1
            
            return instrument_id
    
    def link_performer_instrument(self, conn, performer_id, instrument_id):
        """
        Link a performer to an instrument in performer_instruments table
        Only if the link doesn't already exist
        
        Args:
            conn: Database connection
            performer_id: Performer UUID
            instrument_id: Instrument UUID
        """
        if self.dry_run or not performer_id or not instrument_id:
            return
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO performer_instruments (performer_id, instrument_id, is_primary)
                VALUES (%s, %s, false)
                ON CONFLICT (performer_id, instrument_id) DO NOTHING
            """, (performer_id, instrument_id))
    
    def link_performers_to_recording(self, conn, recording_id, recording_data):
        """
        Link performers (with instruments) to a recording
        
        Args:
            conn: Database connection
            recording_id: Recording UUID (can be None for dry run)
            recording_data: MusicBrainz recording data dict
            
        Returns:
            Number of performers linked
        """
        # Parse artist credits (for fallback if no relationships)
        artists_from_credits = self.parse_artist_credits(recording_data.get('artist-credit', []))
        logger.debug(f"      Parsed {len(artists_from_credits)} artists from recording credits")
        
        # Parse artist relationships to get instrument information
        relations = recording_data.get('relations', [])
        logger.debug(f"      Found {len(relations) if relations else 0} relations in recording data")
        performers_with_instruments = self.parse_artist_relationships(relations)
        logger.debug(f"      Parsed {len(performers_with_instruments)} performers from recording relationships")
        
        # If no good data from recording, try the first release
        if not performers_with_instruments:
            releases = recording_data.get('releases', [])
            if releases:
                first_release_id = releases[0].get('id')
                logger.info(f"      No performer data on recording, checking first release: {first_release_id}")
                
                release_data = self.fetch_release_credits(first_release_id)
                if release_data:
                    mb_recording_id = recording_data.get('id')
                    release_performers = self.parse_release_artist_credits(release_data, mb_recording_id)
                    if release_performers:
                        logger.info(f"      ✓ Found {len(release_performers)} performers from release credits")
                        performers_with_instruments = release_performers
        
        # If we have relationships with instruments, use those; otherwise fall back to credits
        if performers_with_instruments:
            performers_to_import = performers_with_instruments
            logger.debug(f"Using {len(performers_to_import)} performers from relationships (with instruments)")
        else:
            # Convert credits to same format (no instruments)
            performers_to_import = [
                {'name': a['name'], 'mbid': a['mbid'], 'instruments': [], 'role': 'performer'}
                for a in artists_from_credits
            ]
            logger.debug(f"Using {len(performers_to_import)} performers from credits (no instruments)")
        
        if self.dry_run:
            logger.info(f"[DRY RUN]   Performers:")
            for p in performers_to_import:
                role_str = p.get('role', 'performer')
                instruments_str = ', '.join(p['instruments']) if p['instruments'] else f'{role_str} (no instruments)'
                logger.info(f"[DRY RUN]     - {p['name']} ({instruments_str})")
            return len(performers_to_import)
        
        performers_linked = 0
        
        with conn.cursor() as cur:
            # Link performers with instruments
            for i, performer_data in enumerate(performers_to_import):
                performer_id = self.get_or_create_performer(
                    conn,
                    performer_data['name'],
                    performer_data.get('mbid')
                )
                
                if performer_id:
                    # Check if this performer is already linked to this recording
                    cur.execute("""
                        SELECT COUNT(*) as count
                        FROM recording_performers
                        WHERE recording_id = %s AND performer_id = %s
                    """, (recording_id, performer_id))
                    
                    existing_count = cur.fetchone()['count']
                    
                    if existing_count > 0:
                        logger.debug(f"  Skipping {performer_data['name']} - already linked to this recording")
                        continue
                    
                    # Determine role: first performer is leader, others are sidemen
                    # Unless they have a specific role like 'engineer' or 'producer'
                    performer_role = performer_data.get('role', 'performer')
                    
                    if performer_role in ['engineer', 'producer', 'vocal', 'mix', 'mastering']:
                        # These are technical/production roles, not performance roles
                        db_role = 'other'  # Or map to your database's role enum
                    elif i == 0:
                        db_role = 'leader'
                    else:
                        db_role = 'sideman'
                    
                    # Process each instrument for this performer
                    instruments = performer_data.get('instruments', [])
                    
                    if instruments:
                        # Link performer with each instrument they played
                        for instrument_name in instruments:
                            instrument_id = self.get_or_create_instrument(conn, instrument_name)
                            
                            if instrument_id:
                                # Link to recording_performers with instrument
                                cur.execute("""
                                    INSERT INTO recording_performers (
                                        recording_id, performer_id, instrument_id, role
                                    )
                                    VALUES (%s, %s, %s, %s)
                                    ON CONFLICT DO NOTHING
                                """, (recording_id, performer_id, instrument_id, db_role))
                                
                                logger.debug(f"  Linked performer: {performer_data['name']} ({db_role}) - {instrument_name}")
                                
                                # Also link in performer_instruments table (general association)
                                self.link_performer_instrument(conn, performer_id, instrument_id)
                                performers_linked += 1
                    else:
                        # No instrument info, just link the performer without instrument
                        # This handles engineers, producers, or performers without instrument data
                        cur.execute("""
                            INSERT INTO recording_performers (
                                recording_id, performer_id, role
                            )
                            VALUES (%s, %s, %s)
                            ON CONFLICT DO NOTHING
                        """, (recording_id, performer_id, db_role))
                        
                        role_display = performer_role if performer_role != 'performer' else db_role
                        logger.debug(f"  Linked performer: {performer_data['name']} ({role_display}) - no instrument")
                        performers_linked += 1
        
        return performers_linked