//
//  Models.swift
//  JazzReference
//
//  Updated with Repertoire support
//

import Foundation
import SwiftUI

struct Song: Identifiable, Codable {
    let id: String
    let title: String
    let composer: String?
    let structure: String?
    let songReference: String?
    let musicbrainzId: String?
    let wikipediaUrl: String?
    let externalReferences: [String: String]?
    let createdAt: String?
    let updatedAt: String?

    // Recordings data (included in detail view)
    let recordings: [Recording]?
    let recordingCount: Int?

    // NEW: Transcriptions data (now included in song response)
    let transcriptions: [SoloTranscription]?
    let transcriptionCount: Int?

    var authorityRecommendationCount: Int?

    enum CodingKeys: String, CodingKey {
        case id, title, composer, structure
        case songReference = "song_reference"
        case musicbrainzId = "musicbrainz_id"
        case wikipediaUrl = "wikipedia_url"
        case externalReferences = "external_references"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case recordings
        case recordingCount = "recording_count"
        case transcriptions  // NEW
        case transcriptionCount = "transcription_count"  // NEW
        case authorityRecommendationCount = "authority_recommendation_count"
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

struct Recording: Codable, Identifiable {
    let id: String
    let songId: String?
    let songTitle: String?
    let albumTitle: String?
    let recordingDate: String?
    let recordingYear: Int?
    let label: String?
    let spotifyUrl: String?
    let spotifyTrackId: String?
    let albumArtSmall: String?
    let albumArtMedium: String?
    let albumArtLarge: String?
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

    enum CodingKeys: String, CodingKey {
        case id, label, notes, composer, performers
        case songId = "song_id"
        case songTitle = "song_title"
        case albumTitle = "album_title"
        case recordingDate = "recording_date"
        case recordingYear = "recording_year"
        case spotifyUrl = "spotify_url"
        case spotifyTrackId = "spotify_track_id"
        case albumArtSmall = "album_art_small"
        case albumArtMedium = "album_art_medium"
        case albumArtLarge = "album_art_large"
        case youtubeUrl = "youtube_url"
        case appleMusicUrl = "apple_music_url"
        case isCanonical = "is_canonical"
        case musicbrainzId = "musicbrainz_id"
        case authorityCount = "authority_count"
        case authoritySources = "authority_sources"
        case authorityRecommendations = "authority_recommendations"
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
    let instrument: String?
    let role: String?
    let biography: String?
    let birthDate: String?
    let deathDate: String?

    enum CodingKeys: String, CodingKey {
        case id, name, instrument, role, biography
        case birthDate = "birth_date"
        case deathDate = "death_date"
    }
}

struct PerformerDetail: Codable, Identifiable {
    let id: String
    let name: String
    let biography: String?
    let birthDate: String?
    let deathDate: String?
    let externalLinks: [String: String]?
    let wikipediaUrl: String?
    let musicbrainzId: String?
    let instruments: [PerformerInstrument]?
    let recordings: [PerformerRecording]?
    let images: [ArtistImage]?

    enum CodingKeys: String, CodingKey {
        case id, name, biography, instruments, recordings, images
        case birthDate = "birth_date"
        case deathDate = "death_date"
        case externalLinks = "external_links"
        case wikipediaUrl = "wikipedia_url"
        case musicbrainzId = "musicbrainz_id"
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
    let recordingYear: Int?
    let isCanonical: Bool?
    let role: String?

    var id: String { recordingId }

    enum CodingKeys: String, CodingKey {
        case songId = "song_id"
        case songTitle = "song_title"
        case recordingId = "recording_id"
        case albumTitle = "album_title"
        case recordingYear = "recording_year"
        case isCanonical = "is_canonical"
        case role
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

// MARK: - NEW: Repertoire Models

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
}

// Solo Transcriptions - iOS Models and API Methods
// Add these to iOS-app/JazzReference/JazzReferenceApp.swift

// MARK: - Solo Transcription Model

struct SoloTranscription: Codable, Identifiable {
    let id: String
    let songId: String
    let recordingId: String
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
}

// MARK: - Authority Recommendation Model

struct AuthorityRecommendation: Codable, Identifiable {
    let id: String
    let source: String
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
    }

    // Helper properties
    var isMatched: Bool {
        recordingId != nil
    }

    var displayName: String {
        artistName ?? "Unknown Artist"
    }

    var displayAlbum: String {
        matchedAlbumTitle ?? albumTitle ?? "Unknown Album"
    }

    var displayYear: String? {
        if let year = matchedYear ?? recordingYear {
            return "\(year)"
        }
        return nil
    }

    var sourceDisplayName: String {
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

    var sourceColor: Color {
        switch source.lowercased() {
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
// UPDATED: Changed from authority/year/canonical to name/year
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

// MARK: - Preview Data for Solo Transcriptions

#if DEBUG
    extension SoloTranscription {
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
#endif

/// Special repertoire option for "All Songs"
extension Repertoire {
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
