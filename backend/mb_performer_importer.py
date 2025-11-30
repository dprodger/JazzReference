#!/usr/bin/env python3
"""
Shared utilities for importing performer and instrument data from MusicBrainz

UPDATED: Now supports linking performers to releases (not just recordings)
"""

import logging
import re
from db_utils import get_db_connection
from mb_utils import MusicBrainzSearcher


def normalize_group_name(group_name):
    """
    Remove common group suffixes to get the core artist name
    
    Examples:
        "Ahmad Jamal Quintet" → "ahmad jamal"
        "Gene Krupa and His Orchestra" → "gene krupa"
    """
    if not group_name:
        return ""
    
    name = group_name.lower().strip()
    
    # Patterns to remove (order matters - try longest first)
    patterns = [
        r'\s+and\s+his\s+orchestra\b.*$',
        r'\s+and\s+his\s+band\b.*$',
        r'\s+and\s+his\s+quintet\b.*$',
        r'\s+and\s+his\s+quartet\b.*$',
        r'\s+and\s+his\s+trio\b.*$',
        r'\s+orchestra\b.*$',
        r'\s+big\s+band\b.*$',
        r'\s+band\b.*$',
        r'\s+ensemble\b.*$',
        r'\s+trio\b.*$',
        r'\s+quartet\b.*$',
        r'\s+quintet\b.*$',
        r'\s+sextet\b.*$',
        r'\s+septet\b.*$',
        r'\s+octet\b.*$',
    ]
    
    for pattern in patterns:
        name = re.sub(pattern, '', name)
    
    return name.strip()


def is_performer_leader_of_group(performer_name, group_name):
    """
    Check if a performer is likely the leader of a group
    
    Args:
        performer_name: Individual performer name (e.g., "Ahmad Jamal")
        group_name: Group/ensemble name (e.g., "Ahmad Jamal Quintet")
        
    Returns:
        bool: True if the performer is likely the group leader
    """
    if not performer_name or not group_name:
        return False
    
    performer_normalized = performer_name.lower().strip()
    group_normalized = normalize_group_name(group_name)
    
    return performer_normalized == group_normalized


logger = logging.getLogger(__name__)


class PerformerImporter:
    """
    Handles importing performers and instruments from MusicBrainz data
    
    UPDATED: Now supports linking performers to releases via release_performers table
    """
    
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.mb_searcher = MusicBrainzSearcher()
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
        try:
            return self.mb_searcher.get_release_details(release_id)
        except Exception as e:
            logger.warning(f"Error fetching release credits: {e}")
            return None
    
    def link_performers_to_release(self, conn, release_id, mb_recording, release_details):
        """
        Link performers to a release (NEW METHOD)
        
        This extracts performer information from MusicBrainz and creates
        entries in the release_performers table.
        
        Args:
            conn: Database connection (None for dry-run)
            release_id: Our database release ID (None for dry-run)
            mb_recording: MusicBrainz recording data
            release_details: Full MusicBrainz release details
            
        Returns:
            Number of performers linked
        """
        mb_recording_id = mb_recording.get('id') if mb_recording else None
        
        # Extract performers from various sources
        performers_to_import = self._extract_performers(
            mb_recording, release_details, mb_recording_id
        )
        
        if not performers_to_import:
            logger.debug("  No performers found to import")
            return 0
        
        # Get leader information from artist credits
        leader_mbids, leader_names = self._extract_leader_info(mb_recording, release_details)
        
        if self.dry_run:
            self._log_performers_dry_run(performers_to_import, leader_mbids, leader_names)
            return len(performers_to_import)
        
        if not conn or not release_id:
            return 0
        
        performers_linked = 0
        
        with conn.cursor() as cur:
            for performer_data in performers_to_import:
                performer_id = self.get_or_create_performer(
                    conn,
                    performer_data['name'],
                    performer_data.get('mbid')
                )
                
                if not performer_id:
                    continue
                
                # Check if already linked
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM release_performers
                    WHERE release_id = %s AND performer_id = %s
                """, (release_id, performer_id))
                
                if cur.fetchone()['count'] > 0:
                    logger.debug(f"  Skipping {performer_data['name']} - already linked")
                    continue
                
                # Determine role
                db_role = self._determine_role(
                    performer_data, leader_mbids, leader_names
                )
                
                # Process instruments
                instruments = performer_data.get('instruments', [])
                
                if instruments:
                    for instrument_name in instruments:
                        instrument_id = self.get_or_create_instrument(conn, instrument_name)
                        
                        if instrument_id:
                            cur.execute("""
                                INSERT INTO release_performers (
                                    release_id, performer_id, instrument_id, role
                                )
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT DO NOTHING
                            """, (release_id, performer_id, instrument_id, db_role))
                            
                            self.link_performer_instrument(conn, performer_id, instrument_id)
                            performers_linked += 1
                else:
                    # No instrument info
                    cur.execute("""
                        INSERT INTO release_performers (
                            release_id, performer_id, role
                        )
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (release_id, performer_id, db_role))
                    performers_linked += 1
            
            # Ensure at least one leader
            if performers_linked > 0:
                self._ensure_leader_exists(cur, release_id, 'release_performers')
        
        return performers_linked
    
    def link_performers_to_recording(self, conn, recording_id, recording_data):
        """
        Link performers to a recording (LEGACY METHOD - kept for backwards compatibility)
        
        Args:
            conn: Database connection
            recording_id: Our database recording ID
            recording_data: MusicBrainz recording data
            
        Returns:
            Number of performers linked
        """
        # Extract performers from recording data
        performers_to_import = self._extract_performers_from_recording(recording_data)
        
        if not performers_to_import:
            logger.debug("  No performers found to import")
            return 0
        
        # Get leader information from artist credits
        leader_mbids, leader_names = self._extract_leader_info_from_recording(recording_data)
        
        if self.dry_run:
            self._log_performers_dry_run(performers_to_import, leader_mbids, leader_names)
            return len(performers_to_import)
        
        if not conn or not recording_id:
            return 0
        
        performers_linked = 0
        
        with conn.cursor() as cur:
            for performer_data in performers_to_import:
                performer_id = self.get_or_create_performer(
                    conn,
                    performer_data['name'],
                    performer_data.get('mbid')
                )
                
                if not performer_id:
                    continue
                
                # Check if already linked
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM recording_performers
                    WHERE recording_id = %s AND performer_id = %s
                """, (recording_id, performer_id))
                
                if cur.fetchone()['count'] > 0:
                    logger.debug(f"  Skipping {performer_data['name']} - already linked")
                    continue
                
                # Determine role
                db_role = self._determine_role(
                    performer_data, leader_mbids, leader_names
                )
                
                # Process instruments
                instruments = performer_data.get('instruments', [])
                
                if instruments:
                    for instrument_name in instruments:
                        instrument_id = self.get_or_create_instrument(conn, instrument_name)
                        
                        if instrument_id:
                            cur.execute("""
                                INSERT INTO recording_performers (
                                    recording_id, performer_id, instrument_id, role
                                )
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT DO NOTHING
                            """, (recording_id, performer_id, instrument_id, db_role))
                            
                            self.link_performer_instrument(conn, performer_id, instrument_id)
                            performers_linked += 1
                else:
                    cur.execute("""
                        INSERT INTO recording_performers (
                            recording_id, performer_id, role
                        )
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (recording_id, performer_id, db_role))
                    performers_linked += 1
            
            # Ensure at least one leader
            if performers_linked > 0:
                self._ensure_leader_exists(cur, recording_id, 'recording_performers')
        
        return performers_linked
    
    def _extract_performers(self, mb_recording, release_details, target_recording_id=None):
        """
        Extract performers from MusicBrainz data (for releases)
        
        Checks multiple sources:
        1. Recording relationships (artist-rels)
        2. Release relationships
        3. Track-level credits
        4. Artist credits (fallback)
        
        Args:
            mb_recording: MusicBrainz recording data
            release_details: Full release details
            target_recording_id: Recording MBID to match
            
        Returns:
            List of performer dicts with name, mbid, instruments, role
        """
        performers = []
        
        # Try recording-level relationships first
        if mb_recording:
            relations = mb_recording.get('relations', [])
            if relations:
                performers = self.parse_artist_relationships(relations)
                if performers:
                    logger.debug(f"  Found {len(performers)} performers from recording relationships")
                    return performers
        
        # Try release-level relationships
        if release_details:
            # Check track-level credits for the specific recording
            performers = self.parse_release_artist_credits(
                release_details, target_recording_id
            )
            if performers:
                logger.debug(f"  Found {len(performers)} performers from release/track credits")
                return performers
        
        # Fallback to artist credits
        if mb_recording:
            artist_credits = mb_recording.get('artist-credit', [])
            artists = self.parse_artist_credits(artist_credits)
            if artists:
                performers = [
                    {'name': a['name'], 'mbid': a['mbid'], 'instruments': [], 'role': 'performer'}
                    for a in artists
                ]
                logger.debug(f"  Found {len(performers)} performers from artist credits (fallback)")
        
        return performers
    
    def _extract_performers_from_recording(self, recording_data):
        """Extract performers from recording data (legacy method)"""
        performers = []
        
        # Get artist credits
        artist_credits = recording_data.get('artist-credit', [])
        artists_from_credits = self.parse_artist_credits(artist_credits)
        
        # Try to get relationships with instruments
        relations = recording_data.get('relations', [])
        performers_with_instruments = self.parse_artist_relationships(relations)
        
        # If no relationships, try to get from first release
        if not performers_with_instruments:
            releases = recording_data.get('releases', [])
            if releases:
                first_release_id = releases[0].get('id')
                release_data = self.fetch_release_credits(first_release_id)
                if release_data:
                    mb_recording_id = recording_data.get('id')
                    release_performers = self.parse_release_artist_credits(
                        release_data, mb_recording_id
                    )
                    if release_performers:
                        performers_with_instruments = release_performers
        
        # Use relationships if available, otherwise credits
        if performers_with_instruments:
            return performers_with_instruments
        else:
            return [
                {'name': a['name'], 'mbid': a['mbid'], 'instruments': [], 'role': 'performer'}
                for a in artists_from_credits
            ]
    
    def _extract_leader_info(self, mb_recording, release_details):
        """
        Extract leader information from artist credits
        
        Returns:
            Tuple of (leader_mbids set, leader_names set)
        """
        leader_mbids = set()
        leader_names = set()
        
        # From recording
        if mb_recording:
            artist_credits = mb_recording.get('artist-credit', [])
            for credit in artist_credits:
                if isinstance(credit, dict) and 'artist' in credit:
                    artist = credit['artist']
                    if artist.get('id'):
                        leader_mbids.add(artist['id'])
                    if artist.get('name'):
                        leader_names.add(artist['name'].lower())
        
        # From release
        if release_details:
            artist_credits = release_details.get('artist-credit', [])
            for credit in artist_credits:
                if isinstance(credit, dict) and 'artist' in credit:
                    artist = credit['artist']
                    if artist.get('id'):
                        leader_mbids.add(artist['id'])
                    if artist.get('name'):
                        leader_names.add(artist['name'].lower())
        
        return leader_mbids, leader_names
    
    def _extract_leader_info_from_recording(self, recording_data):
        """Extract leader info from recording data (legacy method)"""
        leader_mbids = set()
        leader_names = set()
        
        artist_credits = recording_data.get('artist-credit', [])
        for credit in artist_credits:
            if isinstance(credit, dict) and 'artist' in credit:
                artist = credit['artist']
                if artist.get('id'):
                    leader_mbids.add(artist['id'])
                if artist.get('name'):
                    leader_names.add(artist['name'].lower())
        
        return leader_mbids, leader_names
    
    def _determine_role(self, performer_data, leader_mbids, leader_names):
        """
        Determine the role (leader/sideman/other) for a performer
        
        Args:
            performer_data: Dict with performer info
            leader_mbids: Set of leader MusicBrainz IDs
            leader_names: Set of leader names (lowercase)
            
        Returns:
            Role string: 'leader', 'sideman', or 'other'
        """
        performer_role = performer_data.get('role', 'performer')
        performer_mbid = performer_data.get('mbid')
        performer_name = performer_data.get('name', '')
        
        # Check if technical role
        if performer_role in ['engineer', 'producer', 'mix', 'mastering']:
            return 'other'
        
        # Check if leader by MBID
        if performer_mbid and performer_mbid in leader_mbids:
            return 'leader'
        
        # Check if leader by name
        if performer_name and performer_name.lower() in leader_names:
            return 'leader'
        
        # Check if leader of a group
        for leader_name in leader_names:
            if is_performer_leader_of_group(performer_name, leader_name):
                return 'leader'
        
        return 'sideman'
    
    def _ensure_leader_exists(self, cur, entity_id, table_name):
        """
        Ensure at least one leader exists for a recording/release
        
        Args:
            cur: Database cursor
            entity_id: Recording or release ID
            table_name: 'recording_performers' or 'release_performers'
        """
        id_column = 'recording_id' if table_name == 'recording_performers' else 'release_id'
        
        cur.execute(f"""
            SELECT COUNT(*) as leader_count
            FROM {table_name}
            WHERE {id_column} = %s AND role = 'leader'
        """, (entity_id,))
        
        if cur.fetchone()['leader_count'] == 0:
            logger.debug(f"  No leaders assigned - marking first performer as leader")
            cur.execute(f"""
                UPDATE {table_name}
                SET role = 'leader'
                WHERE id = (
                    SELECT id FROM {table_name}
                    WHERE {id_column} = %s
                    AND role != 'other'
                    ORDER BY id
                    LIMIT 1
                )
            """, (entity_id,))
    
    def _log_performers_dry_run(self, performers, leader_mbids, leader_names):
        """Log performer info for dry-run mode"""
        logger.info(f"  [DRY RUN] Performers ({len(performers)}):")
        for p in performers:
            role = self._determine_role(p, leader_mbids, leader_names)
            instruments = ', '.join(p['instruments']) if p['instruments'] else 'no instrument'
            logger.info(f"    - {p['name']} ({role}) - {instruments}")
    
    # ========================================================================
    # Parsing methods
    # ========================================================================
    
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
        Parse MusicBrainz artist relationships to extract performer and instrument info
        
        Args:
            relations: List of relationship dicts from MusicBrainz
            
        Returns:
            List of dicts with keys: name, mbid, instruments (list), role
        """
        if not relations:
            return []
        
        performers = []
        
        for relation in relations:
            rel_type = relation.get('type', 'unknown')
            target_type = relation.get('target-type', 'unknown')
            
            # Only process artist relationships
            if target_type != 'artist':
                continue
            
            if 'artist' not in relation:
                continue
            
            artist = relation['artist']
            artist_name = artist.get('name')
            artist_mbid = artist.get('id')
            
            if not artist_name:
                continue
            
            instruments = []
            role = rel_type
            
            if rel_type == 'instrument':
                # Extract instrument names from attributes
                attributes = relation.get('attributes', [])
                for attr in attributes:
                    if isinstance(attr, str):
                        instruments.append(attr)
                    elif isinstance(attr, dict) and 'name' in attr:
                        instruments.append(attr['name'])
            elif rel_type == 'vocal':
                instruments.append('vocals')
            elif rel_type not in ['engineer', 'producer', 'mix', 'mastering']:
                continue
            
            performers.append({
                'name': artist_name,
                'mbid': artist_mbid,
                'instruments': instruments,
                'role': role
            })
        
        return performers
    
    def parse_release_artist_credits(self, release_data, target_recording_id=None):
        """
        Parse artist credits from a release, optionally for a specific recording
        
        Args:
            release_data: MusicBrainz release data
            target_recording_id: If provided, only get credits for this recording
            
        Returns:
            List of performer dicts
        """
        performers = []
        
        # Check release-level relationships if not looking for specific recording
        if not target_recording_id:
            relations = release_data.get('relations', [])
            if relations:
                release_performers = self.parse_artist_relationships(relations)
                if release_performers:
                    return release_performers
        
        # Check track-level credits
        media = release_data.get('media', [])
        for medium in media:
            tracks = medium.get('tracks', [])
            for track in tracks:
                recording = track.get('recording', {})
                recording_id = recording.get('id')
                
                if target_recording_id and recording_id != target_recording_id:
                    continue
                
                # Check recording relationships on this track
                recording_relations = recording.get('relations', [])
                if recording_relations:
                    track_performers = self.parse_artist_relationships(recording_relations)
                    if track_performers:
                        performers.extend(track_performers)
                
                # Check track artist credits
                track_artist_credits = track.get('artist-credit', [])
                if track_artist_credits:
                    for credit in track_artist_credits:
                        if 'artist' in credit:
                            artist = credit['artist']
                            performers.append({
                                'name': artist.get('name'),
                                'mbid': artist.get('id'),
                                'instruments': [],
                                'role': 'performer'
                            })
                
                if target_recording_id and recording_id == target_recording_id:
                    break
        
        return performers
    
    # ========================================================================
    # Database helper methods
    # ========================================================================
    
    def get_or_create_performer(self, conn, artist_name, artist_mbid=None):
        """
        Get existing performer or create new one
        
        Args:
            conn: Database connection
            artist_name: Performer name
            artist_mbid: MusicBrainz artist ID (optional)
            
        Returns:
            Performer ID or None
        """
        with conn.cursor() as cur:
            # Try to find by MusicBrainz ID first
            if artist_mbid:
                cur.execute("""
                    SELECT id FROM performers
                    WHERE musicbrainz_id = %s
                """, (artist_mbid,))
                result = cur.fetchone()
                
                if result:
                    return result['id']
            
            # Try to find by name
            cur.execute("""
                SELECT id FROM performers
                WHERE name ILIKE %s
            """, (artist_name,))
            result = cur.fetchone()
            
            if result:
                return result['id']
            
            # Create new performer
            if self.dry_run:
                logger.info(f"  [DRY RUN] Would create performer: {artist_name}")
                return None
            
            cur.execute("""
                INSERT INTO performers (name, musicbrainz_id)
                VALUES (%s, %s)
                RETURNING id
            """, (artist_name, artist_mbid))
            
            performer_id = cur.fetchone()['id']
            logger.info(f"  Created performer: {artist_name}")
            self.stats['performers_created'] += 1
            
            return performer_id
    
    def get_or_create_instrument(self, conn, instrument_name):
        """
        Get existing instrument or create new one
        
        Args:
            conn: Database connection
            instrument_name: Instrument name
            
        Returns:
            Instrument ID or None
        """
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM instruments
                WHERE name ILIKE %s
            """, (instrument_name,))
            result = cur.fetchone()
            
            if result:
                return result['id']
            
            if self.dry_run:
                logger.info(f"  [DRY RUN] Would create instrument: {instrument_name}")
                return None
            
            cur.execute("""
                INSERT INTO instruments (name)
                VALUES (%s)
                RETURNING id
            """, (instrument_name,))
            
            instrument_id = cur.fetchone()['id']
            logger.info(f"  Created instrument: {instrument_name}")
            self.stats['instruments_created'] += 1
            
            return instrument_id
    
    def link_performer_instrument(self, conn, performer_id, instrument_id):
        """
        Link a performer to an instrument in performer_instruments table
        
        Args:
            conn: Database connection
            performer_id: Performer ID
            instrument_id: Instrument ID
        """
        if self.dry_run:
            return
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO performer_instruments (performer_id, instrument_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (performer_id, instrument_id))