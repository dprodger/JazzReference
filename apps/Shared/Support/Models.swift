//
//  Models.swift
//  JazzReference
//
//  UPDATED: Recording-Centric Performer Architecture
//  - Removed dropped columns: spotify_url, spotify_track_id, album_art_small/medium/large
//  - Added: default_release_id
//  - Spotify/album art now comes from releases (via best_* API fields or releases array)
//

import Foundation
import SwiftUI

struct Song: Identifiable, Codable {
    let id: String
    let title: String
    let composer: String?
    let composedYear: Int?
    let composedKey: String?
    let structure: String?
    let songReference: String?
    let musicbrainzId: String?
    let wikipediaUrl: String?
    let externalReferences: [String: String]?
    let createdAt: String?
    let updatedAt: String?

    // Recordings data (included in detail view)
    var recordings: [Recording]?
    let recordingCount: Int?

    // Featured recordings (only authoritative ones, from summary endpoint)
    let featuredRecordings: [Recording]?

    // NEW: Transcriptions data (now included in song response)
    let transcriptions: [SoloTranscription]?
    let transcriptionCount: Int?

    var authorityRecommendationCount: Int?

    // NEW: Whether any recording has streaming links (for play button visibility)
    let hasAnyStreaming: Bool?

    enum CodingKeys: String, CodingKey {
        case id, title, composer, structure
        case composedYear = "composed_year"
        case composedKey = "composed_key"
        case songReference = "song_reference"
        case musicbrainzId = "musicbrainz_id"
        case wikipediaUrl = "wikipedia_url"
        case externalReferences = "external_references"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case recordings
        case recordingCount = "recording_count"
        case featuredRecordings = "featured_recordings"
        case transcriptions
        case transcriptionCount = "transcription_count"
        case authorityRecommendationCount = "authority_recommendation_count"
        case hasAnyStreaming = "has_any_streaming"
    }

    var hasAuthorityRecommendations: Bool {
        guard let count = authorityRecommendationCount else { return false }
        return count > 0
    }

    // Convert external_references JSONB to ExternalReference array
    var externalReferencesList: [ExternalReference] {
        guard let refs = externalReferences else { return [] }
        return refs.map { ExternalReference(source: $0.key, url: $0.value) }
            .sorted { $0.displayName < $1.displayName }
    }
}

// MARK: - Song Recordings Response (from /api/songs/{id}/recordings)
struct SongRecordingsResponse: Codable {
    let songId: String
    let recordings: [Recording]
    let recordingCount: Int

    enum CodingKeys: String, CodingKey {
        case songId = "song_id"
        case recordings
        case recordingCount = "recording_count"
    }
}

// MARK: - Recording Model
// UPDATED: Recording-Centric Architecture
// - Removed: spotifyUrl, spotifyTrackId, albumArtSmall/Medium/Large (dropped from DB)
// - Added: defaultReleaseId
// - Spotify/album art now sourced from releases via best_* API fields

struct Recording: Codable, Identifiable {
    let id: String
    let songId: String?
    let songTitle: String?
    let albumTitle: String?
    let artistCredit: String?  // Artist credit from the default release
    let recordingDate: String?
    let recordingYear: Int?
    let label: String?

    // NEW: Default release for this recording (provides Spotify/album art)
    let defaultReleaseId: String?
    
    // Best cover art from releases (provided by API via subqueries)
    let bestCoverArtSmall: String?
    let bestCoverArtMedium: String?
    let bestCoverArtLarge: String?

    // Album art (from /recordings search endpoint)
    let albumArtSmall: String?
    let albumArtMedium: String?
    let albumArtLarge: String?

    // Back cover art (from Cover Art Archive via release_imagery)
    let backCoverArtSmall: String?
    let backCoverArtMedium: String?
    let backCoverArtLarge: String?
    let hasBackCover: Bool?

    // Album art source info (for watermark/attribution)
    // From recordings endpoint (album_art_source)
    let albumArtSource: String?       // "Spotify", "MusicBrainz", "Apple", etc.
    let albumArtSourceUrl: String?    // Canonical URL at the source
    // From songs endpoint (best_cover_art_source)
    let bestCoverArtSource: String?
    let bestCoverArtSourceUrl: String?
    // Back cover source
    let backCoverSource: String?
    let backCoverSourceUrl: String?

    // Best Spotify URL from releases (provided by API via subqueries)
    let bestSpotifyUrlFromRelease: String?

    // Direct Spotify URL (from /recordings search endpoint)
    let spotifyUrl: String?

    let youtubeUrl: String?
    let appleMusicUrl: String?
    let musicbrainzId: String?
    let isCanonical: Bool?
    let notes: String?
    let performers: [Performer]?
    let composer: String?

    var authorityCount: Int?
    var authoritySources: [String]?
    var authorityRecommendations: [AuthorityRecommendation]?
    
    // Releases this recording appears on (only populated on recording detail)
    let releases: [Release]?

    // Transcriptions for this recording (only populated on recording detail)
    let transcriptions: [SoloTranscription]?

    // NEW: Streaming links by service (spotify, apple_music, youtube)
    let streamingLinks: [String: StreamingLink]?

    // NEW: Whether this recording has any streaming links available
    let hasStreaming: Bool?

    // NEW: Per-service availability flags (for filtering)
    let hasSpotify: Bool?
    let hasAppleMusic: Bool?
    let hasYoutube: Bool?

    // NEW: List of streaming services available for this recording
    let streamingServices: [String]?

    // MARK: - Favorites
    let favoriteCount: Int?
    let isFavorited: Bool?
    let favoritedBy: [FavoriteUser]?

    // MARK: - Community-Contributed Metadata
    let communityData: CommunityData?
    let userContribution: UserContribution?

    enum CodingKeys: String, CodingKey {
        case id, label, notes, composer, performers, releases, transcriptions
        case songId = "song_id"
        case songTitle = "song_title"
        case albumTitle = "album_title"
        case artistCredit = "artist_credit"
        case recordingDate = "recording_date"
        case recordingYear = "recording_year"
        case defaultReleaseId = "default_release_id"
        case bestCoverArtSmall = "best_cover_art_small"
        case bestCoverArtMedium = "best_cover_art_medium"
        case bestCoverArtLarge = "best_cover_art_large"
        case albumArtSmall = "album_art_small"
        case albumArtMedium = "album_art_medium"
        case albumArtLarge = "album_art_large"
        case backCoverArtSmall = "back_cover_art_small"
        case backCoverArtMedium = "back_cover_art_medium"
        case backCoverArtLarge = "back_cover_art_large"
        case hasBackCover = "has_back_cover"
        case albumArtSource = "album_art_source"
        case albumArtSourceUrl = "album_art_source_url"
        case bestCoverArtSource = "best_cover_art_source"
        case bestCoverArtSourceUrl = "best_cover_art_source_url"
        case backCoverSource = "back_cover_source"
        case backCoverSourceUrl = "back_cover_source_url"
        case bestSpotifyUrlFromRelease = "best_spotify_url"
        case spotifyUrl = "spotify_url"
        case youtubeUrl = "youtube_url"
        case appleMusicUrl = "apple_music_url"
        case isCanonical = "is_canonical"
        case musicbrainzId = "musicbrainz_id"
        case authorityCount = "authority_count"
        case authoritySources = "authority_sources"
        case authorityRecommendations = "authority_recommendations"
        case streamingLinks = "streaming_links"
        case hasStreaming = "has_streaming"
        case hasSpotify = "has_spotify"
        case hasAppleMusic = "has_apple_music"
        case hasYoutube = "has_youtube"
        case streamingServices = "streaming_services"
        case favoriteCount = "favorite_count"
        case isFavorited = "is_favorited"
        case favoritedBy = "favorited_by"
        case communityData = "community_data"
        case userContribution = "user_contribution"
    }
    
    // Helper computed properties
    var hasAuthority: Bool {
        guard let count = authorityCount else { return false }
        return count > 0
    }

    var authorityBadgeText: String? {
        guard let count = authorityCount, count > 0 else { return nil }
        if count == 1, let source = authoritySources?.first {
            return authoritySourceDisplayName(source)
        }
        return "\(count) sources"
    }

    var primaryAuthoritySource: String? {
        authoritySources?.first
    }

    private func authoritySourceDisplayName(_ source: String) -> String {
        switch source.lowercased() {
        case "jazzstandards.com":
            return "JazzStandards.com"
        case "allmusic":
            return "AllMusic"
        case "discogs":
            return "Discogs"
        default:
            return source.capitalized
        }
    }
    
    // MARK: - Release-aware computed properties
    
    /// Releases sorted consistently to match songs.py best_cover_art_* selection
    /// Matches: spotify_album_id IS NOT NULL, ORDER BY release_year DESC
    private var sortedReleases: [Release]? {
        releases?.sorted { r1, r2 in
            // First: releases with Spotify come first
            let r1HasSpotify = r1.spotifyAlbumId != nil
            let r2HasSpotify = r2.spotifyAlbumId != nil
            if r1HasSpotify != r2HasSpotify {
                return r1HasSpotify && !r2HasSpotify
            }
            // Second: sort by year DESCENDING (newest first) to match songs.py
            // songs.py uses: ORDER BY rel.release_year DESC NULLS LAST
            switch (r1.releaseYear, r2.releaseYear) {
            case (nil, nil): return false
            case (nil, _): return false  // nil years go last
            case (_, nil): return true
            case let (y1?, y2?): return y1 > y2  // DESCENDING - newest first
            }
        }
    }
    
    /// Get the best Spotify track URL - only returns URLs for track-level matches
    var bestSpotifyUrl: String? {
        // First try direct spotify_url (from /recordings search endpoint)
        if let directUrl = spotifyUrl {
            return directUrl
        }
        // Then try API-provided best URL (from song detail endpoint)
        // This is already track-based (only set when spotify_track_id exists)
        if let apiUrl = bestSpotifyUrlFromRelease {
            return apiUrl
        }
        // Then try sorted releases array (when viewing recording detail)
        // Only use track URLs, not album URLs, for consistency with has_spotify
        if let release = sortedReleases?.first(where: { $0.spotifyTrackUrl != nil }) {
            return release.spotifyTrackUrl
        }
        // No Spotify track URL available
        return nil
    }
    
    /// Get the best album art - prefer API-provided best, then check releases array
    var bestAlbumArtSmall: String? {
        // First try direct album_art (from /recordings search endpoint)
        if let directArt = albumArtSmall {
            return directArt
        }
        // Then try API-provided best URL (from song detail endpoint)
        if let apiArt = bestCoverArtSmall {
            return apiArt
        }
        // Then try sorted releases array (when viewing recording detail)
        if let release = sortedReleases?.first(where: { $0.spotifyAlbumId != nil && $0.coverArtSmall != nil }) {
            return release.coverArtSmall
        }
        // No album art available
        return nil
    }

    var bestAlbumArtMedium: String? {
        if let directArt = albumArtMedium {
            return directArt
        }
        if let apiArt = bestCoverArtMedium {
            return apiArt
        }
        if let release = sortedReleases?.first(where: { $0.spotifyAlbumId != nil && $0.coverArtMedium != nil }) {
            return release.coverArtMedium
        }
        return nil
    }

    var bestAlbumArtLarge: String? {
        if let directArt = albumArtLarge {
            return directArt
        }
        if let apiArt = bestCoverArtLarge {
            return apiArt
        }
        if let release = sortedReleases?.first(where: { $0.spotifyAlbumId != nil && $0.coverArtLarge != nil }) {
            return release.coverArtLarge
        }
        return nil
    }

    /// Get the source of the album art (for watermark attribution)
    var displayAlbumArtSource: String? {
        // First try direct source (from /recordings endpoint)
        if let source = albumArtSource {
            return source
        }
        // Then try API-provided best source (from songs endpoint)
        if let source = bestCoverArtSource {
            return source
        }
        // Then check releases array for source
        if let release = sortedReleases?.first(where: { $0.coverArtSource != nil }) {
            return release.coverArtSource
        }
        return nil
    }

    /// Get the source URL for album art (for attribution links)
    var displayAlbumArtSourceUrl: String? {
        if let url = albumArtSourceUrl {
            return url
        }
        if let url = bestCoverArtSourceUrl {
            return url
        }
        if let release = sortedReleases?.first(where: { $0.coverArtSourceUrl != nil }) {
            return release.coverArtSourceUrl
        }
        return nil
    }

    /// Get the source of the back cover (for watermark attribution)
    var displayBackCoverSource: String? {
        backCoverSource
    }

    /// Get the source URL for back cover (for attribution links)
    var displayBackCoverSourceUrl: String? {
        backCoverSourceUrl
    }

    /// Whether this recording has a back cover available for flipping
    var canFlipToBackCover: Bool {
        hasBackCover == true && backCoverArtMedium != nil
    }

    /// Count of releases with Spotify links
    var spotifyReleaseCount: Int {
        releases?.filter { $0.hasSpotify }.count ?? 0
    }
    
    /// Whether this recording has any releases
    var hasReleases: Bool {
        guard let releases = releases else { return false }
        return !releases.isEmpty
    }

    // MARK: - Streaming Link Helpers

    /// Whether any streaming service is available
    var hasAnyStreamingLink: Bool {
        if let hasStreaming = hasStreaming {
            return hasStreaming
        }
        guard let links = streamingLinks else { return false }
        return !links.isEmpty
    }

    /// Get streaming link for a specific service
    func streamingLink(for service: String) -> StreamingLink? {
        streamingLinks?[service]
    }

    /// Get the best playback URL for the preferred service, with fallback
    func playbackUrl(preferring preferredService: String) -> (service: String, url: String)? {
        // Try preferred service first
        if let link = streamingLinks?[preferredService], let url = link.bestPlaybackUrl {
            return (preferredService, url)
        }
        // Fall back to any available service
        if let links = streamingLinks {
            for (service, link) in links {
                if let url = link.bestPlaybackUrl {
                    return (service, url)
                }
            }
        }
        // Legacy fallback to old URL fields
        if let url = bestSpotifyUrl {
            return ("spotify", url)
        }
        if let url = appleMusicUrl {
            return ("apple_music", url)
        }
        if let url = youtubeUrl {
            return ("youtube", url)
        }
        return nil
    }

    /// Ordered list of available streaming services for UI display
    var availableStreamingServices: [String] {
        if let services = streamingServices {
            return services
        }
        var services: [String] = []
        if let links = streamingLinks {
            services = Array(links.keys).sorted()
        }
        // Add legacy services if not already present
        if bestSpotifyUrl != nil && !services.contains("spotify") {
            services.append("spotify")
        }
        if appleMusicUrl != nil && !services.contains("apple_music") {
            services.append("apple_music")
        }
        if youtubeUrl != nil && !services.contains("youtube") {
            services.append("youtube")
        }
        return services
    }

    // MARK: - Filter Helpers (shared between iOS and Mac)

    /// Whether this recording is playable on any streaming service
    var isPlayable: Bool {
        hasSpotifyAvailable || hasAppleMusicAvailable
    }

    /// Whether this recording is available on Spotify
    var hasSpotifyAvailable: Bool {
        if hasSpotify == true { return true }
        if bestSpotifyUrl != nil { return true }
        if streamingLinks?["spotify"] != nil { return true }
        return false
    }

    /// Whether this recording is available on Apple Music
    var hasAppleMusicAvailable: Bool {
        if hasAppleMusic == true { return true }
        if appleMusicUrl != nil { return true }
        if streamingLinks?["apple_music"] != nil { return true }
        return false
    }
}

// MARK: - Streaming Link Model

struct StreamingLink: Codable {
    let trackUrl: String?
    let albumUrl: String?
    let previewUrl: String?

    enum CodingKeys: String, CodingKey {
        case trackUrl = "track_url"
        case albumUrl = "album_url"
        case previewUrl = "preview_url"
    }

    /// Best available URL for playback (prefer track, fall back to album)
    var bestPlaybackUrl: String? {
        trackUrl ?? albumUrl
    }
}

// MARK: - Community Data Models

/// Consensus values computed from all user contributions
struct CommunityConsensus: Codable {
    let performanceKey: String?
    let tempoMarking: String?
    let isInstrumental: Bool?

    enum CodingKeys: String, CodingKey {
        case performanceKey = "performance_key"
        case tempoMarking = "tempo_marking"
        case isInstrumental = "is_instrumental"
    }
}

/// Contribution counts per field
struct ContributionCounts: Codable {
    let key: Int
    let tempo: Int
    let instrumental: Int
}

/// Container for all community-contributed data
struct CommunityData: Codable {
    let consensus: CommunityConsensus
    let counts: ContributionCounts
}

/// User's own contribution for a recording
struct UserContribution: Codable {
    let performanceKey: String?
    let tempoMarking: String?
    let isInstrumental: Bool?
    let updatedAt: String?

    enum CodingKeys: String, CodingKey {
        case performanceKey = "performance_key"
        case tempoMarking = "tempo_marking"
        case isInstrumental = "is_instrumental"
        case updatedAt = "updated_at"
    }
}

/// Musical key options for contribution form (major and minor)
enum MusicalKey: String, CaseIterable, Identifiable {
    // Major keys
    case c = "C"
    case db = "Db"
    case d = "D"
    case eb = "Eb"
    case e = "E"
    case f = "F"
    case gb = "Gb"
    case g = "G"
    case ab = "Ab"
    case a = "A"
    case bb = "Bb"
    case b = "B"
    // Minor keys
    case cm = "Cm"
    case dbm = "Dbm"
    case dm = "Dm"
    case ebm = "Ebm"
    case em = "Em"
    case fm = "Fm"
    case gbm = "Gbm"
    case gm = "Gm"
    case abm = "Abm"
    case am = "Am"
    case bbm = "Bbm"
    case bm = "Bm"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .c: return "C Major"
        case .db: return "D♭ Major"
        case .d: return "D Major"
        case .eb: return "E♭ Major"
        case .e: return "E Major"
        case .f: return "F Major"
        case .gb: return "G♭ Major"
        case .g: return "G Major"
        case .ab: return "A♭ Major"
        case .a: return "A Major"
        case .bb: return "B♭ Major"
        case .b: return "B Major"
        case .cm: return "C Minor"
        case .dbm: return "D♭ Minor"
        case .dm: return "D Minor"
        case .ebm: return "E♭ Minor"
        case .em: return "E Minor"
        case .fm: return "F Minor"
        case .gbm: return "G♭ Minor"
        case .gm: return "G Minor"
        case .abm: return "A♭ Minor"
        case .am: return "A Minor"
        case .bbm: return "B♭ Minor"
        case .bm: return "B Minor"
        }
    }

    var isMinor: Bool {
        rawValue.hasSuffix("m")
    }

    /// Short display name (e.g., "C" or "Cm")
    var shortName: String { rawValue }
}

/// Tempo marking options for contribution form (standard jazz terms)
enum TempoMarking: String, CaseIterable, Identifiable {
    case ballad = "Ballad"
    case slow = "Slow"
    case medium = "Medium"
    case mediumUp = "Medium-Up"
    case upTempo = "Up-Tempo"
    case fast = "Fast"
    case burning = "Burning"

    var id: String { rawValue }
    var displayName: String { rawValue }

    /// Approximate BPM range for this tempo marking
    var bpmRange: String {
        switch self {
        case .ballad: return "~50-72"
        case .slow: return "~72-108"
        case .medium: return "~108-144"
        case .mediumUp: return "~144-184"
        case .upTempo: return "~184-224"
        case .fast: return "~224-280"
        case .burning: return "280+"
        }
    }
}

// MARK: - Favorite User Model

/// Represents a user who has favorited a recording
struct FavoriteUser: Codable, Identifiable {
    let id: String
    let displayName: String?

    enum CodingKeys: String, CodingKey {
        case id
        case displayName = "display_name"
    }
}

// MARK: - Streaming Service Enum

enum StreamingService: String, CaseIterable, Identifiable {
    case spotify = "spotify"
    case appleMusic = "apple_music"
    case youtube = "youtube"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .spotify: return "Spotify"
        case .appleMusic: return "Apple Music"
        case .youtube: return "YouTube"
        }
    }

    var iconName: String {
        switch self {
        case .spotify: return "music.note.list"
        case .appleMusic: return "music.note"
        case .youtube: return "play.rectangle.fill"
        }
    }

    var brandColor: Color {
        switch self {
        case .spotify: return Color(red: 30/255, green: 215/255, blue: 96/255)  // Spotify green
        case .appleMusic: return Color(red: 252/255, green: 60/255, blue: 68/255)  // Apple Music red
        case .youtube: return Color(red: 255/255, green: 0/255, blue: 0/255)  // YouTube red
        }
    }

    /// URL scheme for opening the app directly
    var urlScheme: String? {
        switch self {
        case .spotify: return "spotify"
        case .appleMusic: return "music"
        case .youtube: return "youtube"
        }
    }

    /// Initialize from a service key string (e.g., "spotify", "apple_music")
    init?(key: String) {
        self.init(rawValue: key)
    }
}

// MARK: - Release Model

struct Release: Identifiable, Codable {
    let id: String
    let title: String
    let artistCredit: String?
    let releaseDate: String?
    let releaseYear: Int?
    let country: String?
    let label: String?
    let catalogNumber: String?
    
    // Spotify integration
    let spotifyAlbumId: String?
    let spotifyAlbumUrl: String?
    let spotifyTrackId: String?
    let spotifyTrackUrl: String?
    
    // Cover art
    let coverArtSmall: String?
    let coverArtMedium: String?
    let coverArtLarge: String?

    // Cover art source (for watermark/attribution)
    let coverArtSource: String?        // "Spotify", "MusicBrainz", "Apple", etc.
    let coverArtSourceUrl: String?     // Canonical URL at source

    // Back cover art (from Cover Art Archive)
    let backCoverArtSmall: String?
    let backCoverArtMedium: String?
    let backCoverArtLarge: String?
    let hasBackCover: Bool?
    let backCoverSource: String?
    let backCoverSourceUrl: String?

    // Track position on release
    let discNumber: Int?
    let trackNumber: Int?
    let totalTracks: Int?
    
    // Format info
    let formatName: String?
    let statusName: String?
    
    // MusicBrainz reference
    let musicbrainzReleaseId: String?
    
    // Performers on this release (when fetched separately)
    let performers: [Performer]?
    let performerCount: Int?
    
    enum CodingKeys: String, CodingKey {
        case id, title, country, label, performers
        case artistCredit = "artist_credit"
        case releaseDate = "release_date"
        case releaseYear = "release_year"
        case catalogNumber = "catalog_number"
        case spotifyAlbumId = "spotify_album_id"
        case spotifyAlbumUrl = "spotify_album_url"
        case spotifyTrackId = "spotify_track_id"
        case spotifyTrackUrl = "spotify_track_url"
        case coverArtSmall = "cover_art_small"
        case coverArtMedium = "cover_art_medium"
        case coverArtLarge = "cover_art_large"
        case coverArtSource = "cover_art_source"
        case coverArtSourceUrl = "cover_art_source_url"
        case backCoverArtSmall = "back_cover_art_small"
        case backCoverArtMedium = "back_cover_art_medium"
        case backCoverArtLarge = "back_cover_art_large"
        case hasBackCover = "has_back_cover"
        case backCoverSource = "back_cover_source"
        case backCoverSourceUrl = "back_cover_source_url"
        case discNumber = "disc_number"
        case trackNumber = "track_number"
        case totalTracks = "total_tracks"
        case formatName = "format_name"
        case statusName = "status_name"
        case musicbrainzReleaseId = "musicbrainz_release_id"
        case performerCount = "performer_count"
    }
    
    // MARK: - Computed Properties

    /// Whether this release has a Spotify track match for the specific recording
    var hasSpotify: Bool {
        spotifyTrackId != nil || spotifyTrackUrl != nil
    }
    
    /// Display string for track position
    var trackPositionDisplay: String? {
        guard let track = trackNumber else { return nil }
        if let disc = discNumber, disc > 1 {
            return "Disc \(disc), Track \(track)"
        }
        return "Track \(track)"
    }
    
    /// Year display string
    var yearDisplay: String {
        if let year = releaseYear {
            return String(year)
        }
        return "Unknown year"
    }
    
    /// Format display with fallback
    var formatDisplay: String {
        formatName ?? "Unknown format"
    }

    /// Whether this release has a back cover available for flipping
    var canFlipToBackCover: Bool {
        hasBackCover == true && backCoverArtMedium != nil
    }
}

struct AuthorityRecommendationsResponse: Codable {
    let songId: String
    let recommendations: [AuthorityRecommendation]
    let totalCount: Int
    let matchedCount: Int
    let unmatchedCount: Int

    enum CodingKeys: String, CodingKey {
        case songId = "song_id"
        case recommendations
        case totalCount = "total_count"
        case matchedCount = "matched_count"
        case unmatchedCount = "unmatched_count"
    }
}

struct Performer: Codable, Identifiable {
    let id: String
    let name: String
    let sortName: String?
    let instrument: String?
    let role: String?
    let biography: String?
    let birthDate: String?
    let deathDate: String?

    enum CodingKeys: String, CodingKey {
        case id, name, instrument, role, biography
        case sortName = "sort_name"
        case birthDate = "birth_date"
        case deathDate = "death_date"
    }
}

struct PerformerDetail: Codable, Identifiable {
    let id: String
    let name: String
    let sortName: String?
    let biography: String?
    let birthDate: String?
    let deathDate: String?
    let externalLinks: [String: String]?
    let wikipediaUrl: String?
    let musicbrainzId: String?
    let instruments: [PerformerInstrument]?
    var recordings: [PerformerRecording]?  // Mutable for two-phase loading
    let images: [ArtistImage]?
    let recordingCount: Int?  // Total count from summary endpoint

    enum CodingKeys: String, CodingKey {
        case id, name, biography, instruments, recordings, images
        case sortName = "sort_name"
        case birthDate = "birth_date"
        case deathDate = "death_date"
        case externalLinks = "external_links"
        case wikipediaUrl = "wikipedia_url"
        case musicbrainzId = "musicbrainz_id"
        case recordingCount = "recording_count"
    }
}

/// Response from /performers/{id}/recordings endpoint
struct PerformerRecordingsResponse: Codable {
    let recordings: [PerformerRecording]
    let recordingCount: Int

    enum CodingKeys: String, CodingKey {
        case recordings
        case recordingCount = "recording_count"
    }
}

struct PerformerInstrument: Codable {
    let name: String
    let isPrimary: Bool?

    enum CodingKeys: String, CodingKey {
        case name
        case isPrimary = "is_primary"
    }
}

struct PerformerRecording: Codable, Identifiable {
    let songId: String
    let songTitle: String
    let recordingId: String
    let albumTitle: String?
    let artistCredit: String?
    let recordingYear: Int?
    let isCanonical: Bool?
    let role: String?
    let bestCoverArtSmall: String?
    let bestCoverArtMedium: String?

    var id: String { recordingId }

    enum CodingKeys: String, CodingKey {
        case songId = "song_id"
        case songTitle = "song_title"
        case recordingId = "recording_id"
        case albumTitle = "album_title"
        case artistCredit = "artist_credit"
        case recordingYear = "recording_year"
        case isCanonical = "is_canonical"
        case role
        case bestCoverArtSmall = "best_cover_art_small"
        case bestCoverArtMedium = "best_cover_art_medium"
    }
}

struct ArtistImage: Codable, Identifiable {
    let id: String
    let url: String
    let source: String
    let sourceIdentifier: String?
    let licenseType: String?
    let licenseUrl: String?
    let attribution: String?
    let width: Int?
    let height: Int?
    let thumbnailUrl: String?
    let sourcePageUrl: String?

    enum CodingKeys: String, CodingKey {
        case id, url, source, width, height, attribution
        case sourceIdentifier = "source_identifier"
        case licenseType = "license_type"
        case licenseUrl = "license_url"
        case thumbnailUrl = "thumbnail_url"
        case sourcePageUrl = "source_page_url"
    }
}

// MARK: - Repertoire Model

/// Represents a named collection of songs (a repertoire)
struct Repertoire: Codable, Identifiable, Hashable {
    let id: String
    let name: String
    let description: String?
    let songCount: Int
    let createdAt: String?
    let updatedAt: String?

    enum CodingKeys: String, CodingKey {
        case id, name, description
        case songCount = "song_count"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }

    // Hashable conformance for use in Picker
    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }

    static func == (lhs: Repertoire, rhs: Repertoire) -> Bool {
        lhs.id == rhs.id
    }
    
    /// Special repertoire option for "All Songs"
    static var allSongs: Repertoire {
        Repertoire(
            id: "all",
            name: "All Songs",
            description: "View all songs in the database",
            songCount: 0,
            createdAt: nil,
            updatedAt: nil
        )
    }
}

// MARK: - Solo Transcription Model

struct SoloTranscription: Codable, Identifiable {
    let id: String
    let songId: String
    let recordingId: String?  // Optional - transcription may be linked to song only
    let youtubeUrl: String?
    let createdAt: String?
    let updatedAt: String?

    // Optional joined data from API
    let songTitle: String?
    let albumTitle: String?
    let recordingYear: Int?
    let composer: String?
    let label: String?

    enum CodingKeys: String, CodingKey {
        case id
        case songId = "song_id"
        case recordingId = "recording_id"
        case youtubeUrl = "youtube_url"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case songTitle = "song_title"
        case albumTitle = "album_title"
        case recordingYear = "recording_year"
        case composer
        case label
    }
    
    // MARK: - Preview Data

    static var preview1: SoloTranscription {
        SoloTranscription(
            id: "preview-transcription-1",
            songId: "preview-song-1",
            recordingId: "preview-recording-1",
            youtubeUrl: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            createdAt: "2024-01-15T10:30:00Z",
            updatedAt: "2024-01-15T10:30:00Z",
            songTitle: "Autumn Leaves",
            albumTitle: "Kind of Blue",
            recordingYear: 1959,
            composer: "Joseph Kosma",
            label: "Columbia"
        )
    }

    static var preview2: SoloTranscription {
        SoloTranscription(
            id: "preview-transcription-2",
            songId: "preview-song-1",
            recordingId: "preview-recording-2",
            youtubeUrl: "https://www.youtube.com/watch?v=abc123xyz",
            createdAt: "2024-02-20T14:15:00Z",
            updatedAt: "2024-02-20T14:15:00Z",
            songTitle: "Autumn Leaves",
            albumTitle: "Waltz for Debby",
            recordingYear: 1961,
            composer: "Joseph Kosma",
            label: "Riverside"
        )
    }

    static var previewMinimal: SoloTranscription {
        SoloTranscription(
            id: "preview-transcription-3",
            songId: "preview-song-2",
            recordingId: "preview-recording-3",
            youtubeUrl: "https://www.youtube.com/watch?v=xyz789abc",
            createdAt: "2024-03-10T09:00:00Z",
            updatedAt: "2024-03-10T09:00:00Z",
            songTitle: "Blue in Green",
            albumTitle: nil,
            recordingYear: nil,
            composer: nil,
            label: nil
        )
    }
}

// MARK: - Video Model (Backing Tracks, Performances, etc.)

struct Video: Codable, Identifiable {
    let id: String
    let songId: String
    let recordingId: String?
    let youtubeUrl: String?
    let title: String?
    let description: String?
    let videoType: String
    let durationSeconds: Int?
    let createdAt: String?
    let updatedAt: String?

    enum CodingKeys: String, CodingKey {
        case id
        case songId = "song_id"
        case recordingId = "recording_id"
        case youtubeUrl = "youtube_url"
        case title, description
        case videoType = "video_type"
        case durationSeconds = "duration_seconds"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }

    // MARK: - Preview Data

    static var preview1: Video {
        Video(
            id: "preview-video-1",
            songId: "preview-song-1",
            recordingId: nil,
            youtubeUrl: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            title: "All of Me - Backing Track in C",
            description: "Professional backing track for practice",
            videoType: "backing_track",
            durationSeconds: 300,
            createdAt: "2024-01-15T10:30:00Z",
            updatedAt: "2024-01-15T10:30:00Z"
        )
    }

    static var preview2: Video {
        Video(
            id: "preview-video-2",
            songId: "preview-song-1",
            recordingId: nil,
            youtubeUrl: "https://www.youtube.com/watch?v=abc123xyz",
            title: "All of Me - Slow Tempo Practice",
            description: nil,
            videoType: "backing_track",
            durationSeconds: 360,
            createdAt: "2024-02-20T14:15:00Z",
            updatedAt: "2024-02-20T14:15:00Z"
        )
    }
}

// MARK: - Authority Recommendation Model

struct AuthorityRecommendation: Codable, Identifiable {
    let id: String
    let source: String?
    let recommendationText: String?
    let sourceUrl: String?
    let artistName: String?
    let albumTitle: String?
    let recordingYear: Int?
    let itunesAlbumId: Int?
    let itunesTrackId: Int?
    let recordingId: String?

    // Optional fields when matched to a recording
    let matchedAlbumTitle: String?
    let matchedYear: Int?
    let matchedSpotifyUrl: String?
    let matchedAlbumArt: String?
    
    // Fields from recording detail endpoint (uses different keys)
    let sourceName: String?
    let recAlbumTitle: String?

    enum CodingKeys: String, CodingKey {
        case id, source
        case recommendationText = "recommendation_text"
        case sourceUrl = "source_url"
        case artistName = "artist_name"
        case albumTitle = "album_title"
        case recordingYear = "recording_year"
        case itunesAlbumId = "itunes_album_id"
        case itunesTrackId = "itunes_track_id"
        case recordingId = "recording_id"
        case matchedAlbumTitle = "matched_album_title"
        case matchedYear = "matched_year"
        case matchedSpotifyUrl = "matched_spotify_url"
        case matchedAlbumArt = "matched_album_art"
        case sourceName = "source_name"
        case recAlbumTitle = "rec_album_title"
    }

    // Helper properties
    var isMatched: Bool {
        recordingId != nil
    }

    var displayName: String {
        artistName ?? "Unknown Artist"
    }

    var displayAlbum: String {
        matchedAlbumTitle ?? albumTitle ?? recAlbumTitle ?? "Unknown Album"
    }

    var displayYear: String? {
        if let year = matchedYear ?? recordingYear {
            return "\(year)"
        }
        return nil
    }

    var sourceDisplayName: String {
        let src = source ?? sourceName ?? ""
        switch src.lowercased() {
        case "jazzstandards.com":
            return "JazzStandards.com"
        case "allmusic":
            return "AllMusic"
        case "discogs":
            return "Discogs"
        default:
            return src.capitalized
        }
    }

    var sourceColor: Color {
        let src = source ?? sourceName ?? ""
        switch src.lowercased() {
        case "jazzstandards.com", "jazzstandards":
            return .blue
        case "ted_gioia":
            return .purple
        case "allmusic":
            return .orange
        default:
            return JazzTheme.brass
        }
    }
}

struct AuthoritiesResponse: Codable {
    let recordingId: String
    let songId: String
    let authorities: [AuthorityRecommendation]
    let count: Int

    enum CodingKeys: String, CodingKey {
        case recordingId = "recording_id"
        case songId = "song_id"
        case authorities
        case count
    }
}

// MARK: - External Reference Model

struct ExternalReference: Identifiable {
    let id = UUID()
    let source: String
    let url: String
    let displayName: String

    init(source: String, url: String) {
        self.source = source
        self.url = url

        // Map source keys to display names
        switch source.lowercased() {
        case "wikipedia":
            self.displayName = "Wikipedia"
        case "jazzstandards":
            self.displayName = "JazzStandards.com"
        case "allmusic":
            self.displayName = "AllMusic"
        case "discogs":
            self.displayName = "Discogs"
        case "musicbrainz":
            self.displayName = "MusicBrainz"
        default:
            self.displayName = source.capitalized
        }
    }

    // Icon for the reference type
    var iconName: String {
        switch source.lowercased() {
        case "wikipedia":
            return "book.fill"
        case "jazzstandards":
            return "music.note.list"
        case "allmusic":
            return "music.quarternote.3"
        case "discogs":
            return "opticaldisc"
        case "musicbrainz":
            return "waveform"
        default:
            return "link"
        }
    }
}

// MARK: - Recording Sort Order Enum

enum RecordingSortOrder: String, CaseIterable, Identifiable {
    case year = "year"
    case name = "name"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .year: return "Year"
        case .name: return "Name"
        }
    }

    var icon: String {
        switch self {
        case .year: return "calendar"
        case .name: return "person.text.rectangle"
        }
    }
}

// MARK: - MusicBrainz Search Models

/// Response from /api/musicbrainz/works/search
struct MusicBrainzSearchResponse: Codable {
    let query: String
    let results: [MusicBrainzWork]
}

/// A work (song) from MusicBrainz search results
struct MusicBrainzWork: Codable, Identifiable {
    let id: String
    let title: String
    let composers: [String]?
    let score: Int?
    let type: String?
    let musicbrainzUrl: String

    enum CodingKeys: String, CodingKey {
        case id, title, composers, score, type
        case musicbrainzUrl = "musicbrainz_url"
    }

    /// Display string for composers
    var composerDisplay: String {
        guard let composers = composers, !composers.isEmpty else {
            return "Unknown composer"
        }
        return composers.joined(separator: ", ")
    }

    /// Match quality description based on score
    var matchQuality: String {
        guard let score = score else { return "" }
        if score >= 90 { return "Excellent match" }
        if score >= 70 { return "Good match" }
        if score >= 50 { return "Possible match" }
        return "Weak match"
    }

    // MARK: - Preview Data

    static var preview1: MusicBrainzWork {
        MusicBrainzWork(
            id: "a74b1b7f-71a5-311f-8151-4c86ebfc8d8e",
            title: "Autumn Leaves",
            composers: ["Joseph Kosma"],
            score: 100,
            type: "Song",
            musicbrainzUrl: "https://musicbrainz.org/work/a74b1b7f-71a5-311f-8151-4c86ebfc8d8e"
        )
    }

    static var preview2: MusicBrainzWork {
        MusicBrainzWork(
            id: "b85c2c8f-82b6-422f-9262-5d97fce9e9f9",
            title: "Giant Steps",
            composers: ["John Coltrane"],
            score: 95,
            type: "Song",
            musicbrainzUrl: "https://musicbrainz.org/work/b85c2c8f-82b6-422f-9262-5d97fce9e9f9"
        )
    }

    static var previewMinimal: MusicBrainzWork {
        MusicBrainzWork(
            id: "c96d3d9f-93c7-533f-a373-6e08gdf0f0f0",
            title: "Autumn Leaves (alternate)",
            composers: nil,
            score: 60,
            type: nil,
            musicbrainzUrl: "https://musicbrainz.org/work/c96d3d9f-93c7-533f-a373-6e08gdf0f0f0"
        )
    }
}

/// Response from /api/musicbrainz/import
struct MusicBrainzImportResponse: Codable {
    let success: Bool
    let message: String
    let song: Song?
    let researchQueued: Bool?
    let queueSize: Int?

    enum CodingKeys: String, CodingKey {
        case success, message, song
        case researchQueued = "research_queued"
        case queueSize = "queue_size"
    }
}
